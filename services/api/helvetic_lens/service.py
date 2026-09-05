import asyncio
import hashlib
import json
import logging
import re
import secrets
import shutil
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, inspect, or_, select
from sqlalchemy.orm import Session

from . import analysis as ai
from . import digests, monitoring_topics, source_packs, synchronization, topic_matching
from . import jobs as durable_jobs
from . import relation_analysis as relation_ai
from .ai_metrics import summarize_ai_triage_metrics
from .assistant_contract import (
    ASSISTANT_CHAT_SCHEMA,
    ASSISTANT_PERSONA_VERSION,
    AssistantChatInput,
    AssistantRemarkInput,
    assistant_chat_messages,
    assistant_remark_messages,
    assistant_remark_schema,
    assistant_route_help,
)
from .broad_official_connector import federal_news_connectors, finma_news_connectors
from .config import DomainError, Settings
from .connectors import CONNECTOR_CONTRACT_VERSION, ConnectorRunner
from .credential_crypto import CredentialCipher
from .db import Database, utcnow
from .deployments import deployment_snapshot
from .diffing import DIFF_SCHEMA_VERSION, compare_passages
from .extraction import (
    Extracted,
    Fetcher,
    canonical_url,
    discover_links,
    extract,
    fedlex_eli_reference,
)
from .federal_court_connector import federal_court_connectors
from .federal_criminal_court_connector import federal_criminal_court_connectors
from .fedlex_connector import fedlex_connectors
from .identity import (
    IDENTITY_REVISION,
    assess_comparison_identity,
    assess_document_identity,
    build_artifact_identity,
)
from .impact_inbox import ImpactInboxFilters, ImpactInboxReader
from .impact_matrix import ImpactMatrixReader
from .integration_logs import IntegrationLogger
from .model_manager_client import ModelManagerClient
from .model_settings import ApertusSettingsInput, public_settings, resolve_key, resolved_settings
from .models import (
    LEGACY_ORGANIZATION_ID,
    ActionDecision,
    AdministrativeAudit,
    Analysis,
    ApertusConfiguration,
    AskRecord,
    Comparison,
    ConnectorState,
    DigestDelivery,
    DigestPreference,
    DocumentWatch,
    IdentityDecision,
    IntegrationLog,
    Job,
    JobStep,
    Law,
    LegacyDocumentMapping,
    Observation,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationQuota,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    OutboxMessage,
    PlatformPromptConfiguration,
    Profile,
    PromptConfiguration,
    PromptRevision,
    RegulatoryDate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
    Scan,
    ScanItem,
    Source,
    User,
    Version,
)
from .observability import ApiMetrics, correlation_context, enrich_correlation
from .official_notices_connector import ParliamentNoticeConnector
from .official_source_contracts import OFFICIAL_SOURCE_CONTRACTS
from .parliament_connector import parliament_connectors
from .prompt_settings import (
    PromptSettingsInput,
    default_prompt_settings,
    public_prompt_settings,
    resolved_prompt_settings,
)
from .registry import RegistryFilters, RegistryReader
from .regulatory_corpus import RegulatoryCorpus
from .source_capabilities import capability_catalogue

logger = logging.getLogger(__name__)
DISCOVERY_TIMEOUT_SECONDS = 120
DISCOVERY_CONCURRENCY = 3


def as_dict(record, omit=()) -> dict:
    result = {}
    for attr in inspect(record).mapper.column_attrs:
        if attr.key in omit:
            continue
        value = getattr(record, attr.key)
        if isinstance(value, datetime):
            value = (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()
        result[attr.key] = value
    return result


def get(session: Session, model, item_id: str):
    record = session.get(model, item_id)
    if record is None:
        raise DomainError("The requested record was not found.", 404, "not_found")
    return record


def version_summary(version: Version) -> dict:
    return {
        **as_dict(version, {"text", "passages", "artifact_key"}),
        "characters": len(version.text),
        "passage_count": len(version.passages),
        "page_count": max((p.get("page") or 0 for p in version.passages), default=0),
        "evidence_url": f"/evidence/{version.id}",
        "artifact_url": f"/api/versions/{version.id}/artifact",
    }


class HelveticLens:
    def __init__(
        self,
        settings: Settings,
        fetcher=None,
        model_client=None,
        model_manager_client=None,
        organization_id: str = LEGACY_ORGANIZATION_ID,
        organization_name: str = "Legacy workspace",
    ):
        self._runtime_active = ContextVar(f"helvetic_lens_runtime_{id(self)}", default=False)
        self._settings_context = ContextVar(f"helvetic_lens_settings_{id(self)}", default=None)
        self._model_client_context = ContextVar(f"helvetic_lens_model_{id(self)}", default=None)
        self._prompt_context = ContextVar(f"helvetic_lens_prompts_{id(self)}", default=None)
        self._prompt_revision_context = ContextVar(
            f"helvetic_lens_prompt_revision_{id(self)}", default=None
        )
        self._fallback_settings = settings
        self.environment_settings = settings.model_copy(deep=True)
        self.default_organization_id = organization_id
        self.organization_name = organization_name
        self.db = Database(settings, organization_id)
        self.credential_cipher = CredentialCipher(settings)
        self.integration_logger = IntegrationLogger(self.db.session)
        self.api_metrics = ApiMetrics()
        self.regulatory_corpus = RegulatoryCorpus()
        self.connector_runner = ConnectorRunner(self.db, self.regulatory_corpus, settings)
        self.fetcher = fetcher or Fetcher(settings, self.integration_logger)
        self._provided_model_client = model_client is not None
        self._fallback_model_client = model_client or ai.ModelClient(settings, self.integration_logger)
        self.model_manager = model_manager_client or ModelManagerClient(settings)
        self._fallback_prompt_settings = default_prompt_settings()
        self._fallback_prompt_revision = 1
        self.write_guard = threading.RLock()
        self.analysis_locks: dict[str, asyncio.Lock] = {}
        self.ask_locks: dict[str, asyncio.Lock] = {}

    @property
    def organization_id(self) -> str:
        return self.db.current_organization_id

    @property
    def settings(self) -> Settings:
        return self._settings_context.get() or self._fallback_settings

    @settings.setter
    def settings(self, value: Settings):
        if self._runtime_active.get():
            self._settings_context.set(value)
        else:
            self._fallback_settings = value

    @property
    def model_client(self):
        return self._model_client_context.get() or self._fallback_model_client

    @model_client.setter
    def model_client(self, value):
        if self._runtime_active.get():
            self._model_client_context.set(value)
        else:
            self._fallback_model_client = value

    @property
    def prompt_settings(self):
        return self._prompt_context.get() or self._fallback_prompt_settings

    @prompt_settings.setter
    def prompt_settings(self, value):
        if self._runtime_active.get():
            self._prompt_context.set(value)
        else:
            self._fallback_prompt_settings = value

    @property
    def prompt_revision(self) -> int:
        return self._prompt_revision_context.get() or self._fallback_prompt_revision

    @prompt_revision.setter
    def prompt_revision(self, value: int):
        if self._runtime_active.get():
            self._prompt_revision_context.set(value)
        else:
            self._fallback_prompt_revision = value

    @contextmanager
    def organization_runtime(self):
        with self.db.session() as session:
            model_record = session.get(ApertusConfiguration, self.tenant_record_id)
            prompt_record = session.get(PromptConfiguration, self.tenant_record_id)
            platform_prompt = session.get(PlatformPromptConfiguration, "default")
            settings = resolved_settings(
                self.environment_settings,
                model_record,
                decrypt_secret=self.credential_cipher.decrypt,
            )
            # A caller-supplied model client (tests and embedded deployments) may
            # also adjust its matching fallback settings at runtime. Preserve that
            # pair for the legacy developer workspace when no persisted provider
            # configuration exists.
            if (
                self._provided_model_client
                and self.organization_id == self.default_organization_id
                and model_record is None
            ):
                settings = self._fallback_settings
            effective_prompt = prompt_record or platform_prompt
            prompts = resolved_prompt_settings(effective_prompt)
            revision = effective_prompt.revision if effective_prompt else 1
        client = (
            self._fallback_model_client
            if self._provided_model_client
            else ai.ModelClient(settings, self.integration_logger)
        )
        active_token = self._runtime_active.set(True)
        setting_token = self._settings_context.set(settings)
        model_token = self._model_client_context.set(client)
        prompt_token = self._prompt_context.set(prompts)
        revision_token = self._prompt_revision_context.set(revision)
        try:
            yield
        finally:
            self._prompt_revision_context.reset(revision_token)
            self._prompt_context.reset(prompt_token)
            self._model_client_context.reset(model_token)
            self._settings_context.reset(setting_token)
            self._runtime_active.reset(active_token)

    @property
    def tenant_record_id(self) -> str:
        return "default" if self.organization_id == LEGACY_ORGANIZATION_ID else self.organization_id

    @staticmethod
    def is_shared_official_url(url: str) -> bool:
        return fedlex_eli_reference(url) is not None

    @staticmethod
    def canonical_document_identity(url: str) -> str:
        reference = fedlex_eli_reference(url)
        return reference.work_uri if reference else url.lower()

    def watch(self, session: Session, law_id: str, *, required: bool = True) -> DocumentWatch | None:
        record = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        if record is None and required:
            raise DomainError("The requested record was not found.", 404, "not_found")
        return record

    def initialize(self):
        self.db.migrate()
        with self.db.session(include_all_organizations=True) as session:
            changed = False
            for record in session.scalars(select(ApertusConfiguration)):
                if (
                    record.key_source == "saved"
                    and record.api_key
                    and not self.credential_cipher.is_encrypted(record.api_key)
                ):
                    record.api_key = self.credential_cipher.encrypt(record.api_key)
                    record.updated_at = utcnow()
                    changed = True
            if changed:
                session.commit()
        with self.db.session() as session:
            if not session.get(Organization, self.organization_id):
                session.add(
                    Organization(
                        id=self.organization_id,
                        name=self.organization_name,
                        slug=f"organization-{self.organization_id}",
                    )
                )
                session.flush()
            if not session.get(Profile, self.tenant_record_id):
                session.add(Profile(id=self.tenant_record_id))
            if not session.scalar(select(OrganizationQuota)):
                session.add(OrganizationQuota(values={}))
            synchronization.seed_schedules(session)
            source_packs.seed_definitions(session)
            active_job_states = ["queued", "dispatched", "running", "retrying", "waiting_for_model"]
            for scan in session.scalars(select(Scan).where(Scan.status.in_(["queued", "running"]))):
                durable_job = session.scalar(
                    select(Job).where(
                        Job.type == "scan",
                        Job.target_type == "scan",
                        Job.target_id == scan.id,
                        Job.state.in_(active_job_states),
                    )
                )
                if durable_job:
                    if durable_job.state != "running":
                        scan.status = "queued"
                    for item in session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)):
                        if item.stage not in {"complete", "failed"}:
                            item.stage = "queued"
                            item.error = None
                    continue
                scan.status, scan.finished_at = "interrupted", utcnow()
                for item in session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)):
                    if item.stage not in {"complete", "failed"}:
                        item.stage, item.error = (
                            "interrupted",
                            "The API restarted before this item completed. Retry the scan.",
                        )
                        if item.analysis_status == "pending":
                            item.analysis_status = "interrupted"
            active_impact_targets = select(Job.target_id).where(
                Job.type == "impact_analysis", Job.state.in_(active_job_states)
            )
            for analysis in session.scalars(
                select(Analysis).where(
                    Analysis.status == "pending",
                    Analysis.comparison_id.not_in(active_impact_targets),
                )
            ):
                analysis.status, analysis.error = (
                    "failed",
                    "Analysis was interrupted by a service restart. Retry it.",
                )
            active_ask_targets = select(Job.target_id).where(
                Job.type == "ask", Job.state.in_(active_job_states)
            )
            for record in session.scalars(
                select(AskRecord).where(
                    AskRecord.status == "pending",
                    AskRecord.comparison_id.not_in(active_ask_targets),
                )
            ):
                record.status, record.error = (
                    "failed",
                    "The question was interrupted by a service restart. Ask it again to retry.",
                )
            durable_jobs.reconcile(session, self.settings.job_lease_seconds)
            session.commit()
            saved = session.get(ApertusConfiguration, self.tenant_record_id)
            if saved:
                self.apply_model_settings(
                    resolved_settings(
                        self.environment_settings,
                        saved,
                        decrypt_secret=self.credential_cipher.decrypt,
                    )
                )
            prompt_record = session.get(PromptConfiguration, self.tenant_record_id)
            platform_prompt = session.get(PlatformPromptConfiguration, "default")
            effective_prompt = prompt_record or platform_prompt
            self.prompt_settings = resolved_prompt_settings(effective_prompt)
            self.prompt_revision = effective_prompt.revision if effective_prompt else 1
            for version in session.scalars(select(Version)):
                law = session.get(Law, version.law_id)
                if law:
                    self.refresh_version_identity(session, law, version)
            for comparison in session.scalars(select(Comparison)):
                self.refresh_comparison_identity(session, comparison)
            session.commit()

    def apply_model_settings(self, settings: Settings):
        current_client = self.model_client
        next_client = (
            ai.ModelClient(settings, self.integration_logger)
            if isinstance(current_client, ai.ModelClient)
            else current_client
        )
        if self.organization_id == self.default_organization_id:
            self._fallback_settings = settings
            self._fallback_model_client = next_client
        if self._runtime_active.get():
            self._settings_context.set(settings)
            self._model_client_context.set(next_client)

    async def inference_provenance(self, settings: Settings, trace: list[dict]) -> dict:
        deployment, hardware = {}, {}
        if settings.apertus_provider == "docker":
            try:
                inventory = await self.model_manager.inventory()
                deployment = inventory.get("deployment") or {}
                hardware = inventory.get("hardware") or {}
            except DomainError as exc:
                deployment = {"state": "unavailable", "error_code": exc.code}
        calls = [event for event in trace if event.get("outcome")]
        usage: dict[str, int] = {}
        for event in calls:
            for key, value in (event.get("usage") or {}).items():
                if isinstance(value, int):
                    usage[key] = usage.get(key, 0) + value
        validations = [event for event in trace if event.get("validation")]
        return {
            "backend": settings.apertus_provider,
            "model": settings.apertus_model,
            "model_revision": deployment.get("model_revision"),
            "artifact_sha256": deployment.get("artifact_sha256"),
            "quantization": deployment.get("quantization"),
            "runtime_version": deployment.get("runtime_image"),
            "hardware_profile": deployment.get("hardware_profile"),
            "hardware": {
                "cuda_devices": hardware.get("cuda_devices", []),
                "ram_bytes": hardware.get("ram_bytes"),
            },
            "context": {
                "configured_chars": settings.apertus_context_chars,
                "runtime_tokens": deployment.get("context_size"),
            },
            "generation": {
                "max_tokens": settings.apertus_max_tokens,
                "temperature": settings.apertus_temperature,
                "top_p": settings.apertus_top_p,
                "presence_penalty": settings.apertus_presence_penalty,
                "reasoning_effort": settings.apertus_reasoning_effort,
            },
            "queue_wait_ms": round(sum(event.get("queue_wait_ms", 0) for event in calls), 2),
            "inference_duration_ms": round(sum(event.get("duration_ms", 0) for event in calls), 2),
            "token_counts": usage,
            "provider_calls": len(calls),
            "attempts": calls,
            "validation": {
                "accepted": bool(validations) and all(v.get("validation") == "accepted" for v in validations),
                "repair_count": sum(1 for value in validations if value.get("repair")),
                "events": validations,
            },
        }

    def apertus_configuration(self):
        with self.db.session() as session:
            saved = session.get(ApertusConfiguration, self.tenant_record_id)
            return public_settings(self.settings, saved)

    def save_model_settings(self, data: ApertusSettingsInput):
        with self.write_guard, self.db.session() as session:
            saved = session.get(ApertusConfiguration, self.tenant_record_id)
            next_settings = resolved_settings(
                self.environment_settings,
                saved,
                data,
                decrypt_secret=self.credential_cipher.decrypt,
            )
            key_source, stored_key, _ = resolve_key(
                self.environment_settings,
                saved,
                data,
                self.credential_cipher.decrypt,
            )
            if saved is None:
                saved = ApertusConfiguration(id=self.tenant_record_id)
                session.add(saved)
            saved.values = data.public_values()
            saved.key_source = key_source
            saved.api_key = self.credential_cipher.encrypt(stored_key) if key_source == "saved" else None
            saved.updated_at = utcnow()
            session.commit()
            self.apply_model_settings(next_settings)
            return public_settings(self.settings, saved)

    def reset_model_settings(self):
        with self.write_guard, self.db.session() as session:
            saved = session.get(ApertusConfiguration, self.tenant_record_id)
            if saved:
                session.delete(saved)
                session.commit()
            self.apply_model_settings(self.environment_settings.model_copy(deep=True))
            return public_settings(self.settings, None)

    def prompt_configuration(self):
        with self.db.session() as session:
            record = session.get(PromptConfiguration, self.tenant_record_id)
            platform = session.get(PlatformPromptConfiguration, "default")
            effective_record = record or platform
            result = public_prompt_settings(self.prompt_settings, effective_record)
            source = "workspace" if record else "platform_default" if platform else "defaults"
            return {**result, "source": source}

    def save_prompt_settings(self, data: PromptSettingsInput):
        with self.write_guard, self.db.session() as session:
            record = session.get(PromptConfiguration, self.tenant_record_id)
            if record is None:
                record = PromptConfiguration(id=self.tenant_record_id, revision=1)
                session.add(record)
            else:
                record.revision += 1
            record.values = data.model_dump()
            record.updated_at = utcnow()
            session.add(PromptRevision(revision=record.revision, values=record.values))
            session.commit()
            self.prompt_settings = data.model_copy(deep=True)
            self.prompt_revision = record.revision
            if self.organization_id == self.default_organization_id:
                self._fallback_prompt_settings = data.model_copy(deep=True)
                self._fallback_prompt_revision = record.revision
            return public_prompt_settings(self.prompt_settings, record)

    def reset_prompt_settings(self):
        with self.write_guard, self.db.session() as session:
            record = session.get(PromptConfiguration, self.tenant_record_id)
            if record:
                session.delete(record)
                session.commit()
            platform = session.get(PlatformPromptConfiguration, "default")
            effective = resolved_prompt_settings(platform)
            revision = platform.revision if platform else 1
            self.prompt_settings = effective
            self.prompt_revision = revision
            if self.organization_id == self.default_organization_id:
                self._fallback_prompt_settings = effective
                self._fallback_prompt_revision = revision
            result = public_prompt_settings(effective, platform)
            return {**result, "source": "platform_default" if platform else "defaults"}

    def platform_prompt_configuration(self):
        with self.db.session(include_all_organizations=True) as session:
            record = session.get(PlatformPromptConfiguration, "default")
            result = public_prompt_settings(resolved_prompt_settings(record), record)
            return {**result, "scope": "platform_default"}

    def save_platform_prompt_settings(self, data: PromptSettingsInput):
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            record = session.get(PlatformPromptConfiguration, "default")
            if record is None:
                record = PlatformPromptConfiguration(id="default", revision=1)
                session.add(record)
            else:
                record.revision += 1
            record.values = data.model_dump()
            record.updated_at = utcnow()
            session.commit()
            result = public_prompt_settings(resolved_prompt_settings(record), record)
            return {**result, "scope": "platform_default"}

    def reset_platform_prompt_settings(self):
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            record = session.get(PlatformPromptConfiguration, "default")
            if record:
                session.delete(record)
                session.commit()
            result = public_prompt_settings(default_prompt_settings(), None)
            return {**result, "scope": "built_in_default"}

    async def test_model_settings(self, data: ApertusSettingsInput | None = None):
        if data is not None:
            with self.db.session() as session:
                saved = session.get(ApertusConfiguration, self.tenant_record_id)
                settings = resolved_settings(
                    self.environment_settings,
                    saved,
                    data,
                    decrypt_secret=self.credential_cipher.decrypt,
                )
            model_client = ai.ModelClient(settings, self.integration_logger)
        else:
            settings, model_client = self.settings, self.model_client
        start = time.monotonic()
        reply = await model_client.complete(
            "Return only a JSON object with a status field equal to ok.",
            "Test the Helvetic Lens connection.",
            response_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"status": {"type": "string", "const": "ok"}},
                "required": ["status"],
            },
        )
        return {
            "status": "connected",
            "model": settings.apertus_model,
            "base_url": settings.apertus_base_url,
            "latency_ms": round((time.monotonic() - start) * 1000),
            "received_reply": bool(reply.strip()),
            "saved": data is None,
        }

    async def list_model_settings(self, data: ApertusSettingsInput):
        with self.db.session() as session:
            saved = session.get(ApertusConfiguration, self.tenant_record_id)
            settings = resolved_settings(
                self.environment_settings,
                saved,
                data,
                decrypt_secret=self.credential_cipher.decrypt,
            )
        models = await ai.ModelClient(settings, self.integration_logger).models()
        return {
            "provider": settings.apertus_provider,
            "base_url": settings.apertus_base_url,
            "models": models,
            "count": len(models),
            "saved": False,
        }

    async def preview(self, url: str, provider: str = "native", *, boundary: tuple[str, str] | None = None):
        fetched = await self.fetcher.fetch(canonical_url(url), provider, boundary=boundary)
        name = PurePosixPath(urlsplit(fetched.url).path).name or "document.html"
        extracted = await asyncio.to_thread(extract, fetched.body, fetched.content_type, name, provider)
        return {**extracted.preview(), "url": fetched.url, "metadata": fetched.metadata}

    def save_snapshot(
        self,
        session: Session,
        law: Law,
        document: Extracted,
        origin: str,
        source_url: str | None = None,
        declared_date: str | None = None,
        synthetic: bool = False,
        metadata: dict | None = None,
    ) -> tuple[Version, bool]:
        if declared_date:
            try:
                date.fromisoformat(declared_date)
            except ValueError as exc:
                raise DomainError("Use YYYY-MM-DD for the optional version date.") from exc
        extension = {"application/pdf": ".pdf", "text/html": ".html"}.get(document.content_type, ".txt")
        artifact_key = hashlib.sha256(document.body).hexdigest() + extension
        folder = self.settings.storage_path / "artifacts"
        folder.mkdir(parents=True, exist_ok=True)
        artifact = folder / artifact_key
        if not artifact.exists():
            artifact.write_bytes(document.body)
        owner_organization_id = (
            None if law.owner_organization_id is None and origin == "live" else self.organization_id
        )
        owner_match = (
            Version.owner_organization_id.is_(None)
            if owner_organization_id is None
            else Version.owner_organization_id == owner_organization_id
        )
        version = session.scalar(
            select(Version).where(
                Version.law_id == law.id,
                Version.content_hash == document.content_hash,
                Version.extractor == document.extractor,
                owner_match,
            )
        )
        reused = version is not None
        if version is None:
            version = Version(
                owner_organization_id=owner_organization_id,
                law_id=law.id,
                title=document.title,
                content_hash=document.content_hash,
                extractor=document.extractor,
                text=document.text,
                passages=document.passages,
                content_type=document.content_type,
                artifact_key=artifact_key,
                filename=document.filename,
                source_url=source_url,
                origin=origin,
                declared_date=declared_date,
                date_provenance="user_supplied" if declared_date else None,
                synthetic=synthetic,
            )
            session.add(version)
            session.flush()
        if not reused or (version.identity_json or {}).get("revision") != IDENTITY_REVISION:
            version.identity_json = build_artifact_identity(
                title=document.title,
                source_url=source_url,
                passages=document.passages,
                extractor=document.extractor,
                content_type=document.content_type,
                filename=document.filename,
                declared_date=declared_date,
                metadata=metadata,
            )
        session.add(
            Observation(
                law_id=law.id,
                version_id=version.id,
                origin=origin,
                source_url=source_url,
                filename=document.filename,
                artifact_key=artifact_key,
                declared_date=declared_date,
                synthetic=synthetic,
                metadata_json=metadata or {},
            )
        )
        return version, reused

    def refresh_version_identity(self, session: Session, law: Law, version: Version) -> dict:
        identity = version.identity_json or {}
        if identity.get("revision") != IDENTITY_REVISION:
            observation = session.scalar(
                select(Observation)
                .where(Observation.version_id == version.id)
                .order_by(Observation.created_at.desc())
                .limit(1)
            )
            identity = build_artifact_identity(
                title=version.title,
                source_url=(observation.source_url if observation else version.source_url),
                passages=version.passages,
                extractor=version.extractor,
                content_type=version.content_type,
                filename=version.filename,
                declared_date=(observation.declared_date if observation else version.declared_date),
                metadata=(observation.metadata_json if observation else {}),
            )
            version.identity_json = identity
            session.flush()
        return assess_document_identity(
            law_name=law.name,
            law_url=law.url,
            title=version.title,
            source_url=version.source_url,
            passages=version.passages,
            artifact_identity=identity,
        )

    @staticmethod
    def identity_confirmed(session: Session, version: Version, report: dict) -> bool:
        return bool(
            report["status"] == "unknown"
            and session.scalar(
                select(IdentityDecision.id).where(
                    IdentityDecision.version_id == version.id,
                    IdentityDecision.action == "confirm_assignment",
                    IdentityDecision.identity_fingerprint == report["fingerprint"],
                ).limit(1)
            )
        )

    def refresh_comparison_identity(self, session: Session, comparison: Comparison) -> dict:
        law = get(session, Law, comparison.law_id)
        old = get(session, Version, comparison.old_version_id)
        new = get(session, Version, comparison.new_version_id)
        self.refresh_version_identity(session, law, old)
        self.refresh_version_identity(session, law, new)
        report = assess_comparison_identity(law, old, new)
        confirmed = []
        for side, version in (("old", old), ("new", new)):
            if self.identity_confirmed(session, version, report[side]):
                report[side]["user_confirmed"] = True
                confirmed.append(side)
        if report["status"] == "unknown" and all(
            item["status"] != "unknown" or item.get("user_confirmed")
            for item in (report["old"], report["new"])
        ):
            report["effective_status"] = "probable"
            report["reason_code"] = "assignments_confirmed"
            report["reason"] = "Unknown artifact assignments were explicitly confirmed and recorded for review."
        else:
            report["effective_status"] = report["status"]
        report["confirmed_sides"] = confirmed
        comparison.identity_json = report
        session.flush()
        return report

    def record_identity_decision(
        self, session: Session, law: Law, version: Version, report: dict, action: str, note: str | None = None
    ) -> IdentityDecision:
        if action == "confirm_assignment" and report["status"] != "unknown":
            raise DomainError(
                "Only an unknown assignment can be confirmed. A contradictory official identifier must be corrected.",
                409,
                "identity_decision_not_allowed",
            )
        existing = session.scalar(
            select(IdentityDecision).where(
                IdentityDecision.version_id == version.id,
                IdentityDecision.action == action,
                IdentityDecision.identity_fingerprint == report["fingerprint"],
            ).limit(1)
        )
        if existing:
            return existing
        decision = IdentityDecision(
            law_id=law.id,
            version_id=version.id,
            action=action,
            identity_fingerprint=report["fingerprint"],
            note=(note or "")[:1000] or None,
        )
        session.add(decision)
        session.flush()
        return decision

    def confirm_version_identity(self, version_id: str, note: str | None = None):
        with self.write_guard, self.db.session() as session:
            version = get(session, Version, version_id)
            law = get(session, Law, version.law_id)
            report = self.refresh_version_identity(session, law, version)
            decision = self.record_identity_decision(
                session, law, version, report, "confirm_assignment", note
            )
            for comparison in session.scalars(
                select(Comparison).where(
                    (Comparison.old_version_id == version.id)
                    | (Comparison.new_version_id == version.id)
                )
            ):
                self.refresh_comparison_identity(session, comparison)
            session.commit()
            return {"decision": as_dict(decision), "identity": report}

    def delete_version(self, version_id: str):
        with self.write_guard, self.db.session() as session:
            version = get(session, Version, version_id)
            law = get(session, Law, version.law_id)
            if law.current_version_id == version.id:
                raise DomainError(
                    "The current live snapshot cannot be removed. Fetch or select a correct live version first.",
                    409,
                    "current_version_delete_blocked",
                )
            for watch in session.scalars(
                select(DocumentWatch).where(DocumentWatch.selected_baseline_version_id == version.id)
            ):
                watch.selected_baseline_version_id = None
            comparisons = list(
                session.scalars(
                    select(Comparison).where(
                        (Comparison.old_version_id == version.id)
                        | (Comparison.new_version_id == version.id)
                    )
                )
            )
            comparison_ids = [comparison.id for comparison in comparisons]
            if comparison_ids:
                session.execute(delete(AskRecord).where(AskRecord.comparison_id.in_(comparison_ids)))
                session.execute(delete(Analysis).where(Analysis.comparison_id.in_(comparison_ids)))
                for item in session.scalars(
                    select(ScanItem).where(
                        (ScanItem.comparison_id.in_(comparison_ids))
                        | (ScanItem.monitoring_comparison_id.in_(comparison_ids))
                    )
                ):
                    if item.comparison_id in comparison_ids:
                        item.comparison_id = None
                    if item.monitoring_comparison_id in comparison_ids:
                        item.monitoring_comparison_id = None
                session.execute(delete(Comparison).where(Comparison.id.in_(comparison_ids)))
            for item in session.scalars(
                select(ScanItem).where(
                    (ScanItem.baseline_version_id == version.id) | (ScanItem.new_version_id == version.id)
                )
            ):
                if item.baseline_version_id == version.id:
                    item.baseline_version_id = None
                if item.new_version_id == version.id:
                    item.new_version_id = None
            session.execute(delete(IdentityDecision).where(IdentityDecision.version_id == version.id))
            session.execute(delete(Observation).where(Observation.version_id == version.id))
            artifact_key = version.artifact_key
            session.delete(version)
            session.commit()
            referenced = session.scalar(
                select(Version.id).where(Version.artifact_key == artifact_key).limit(1)
            ) or session.scalar(
                select(Observation.id).where(Observation.artifact_key == artifact_key).limit(1)
            )
        if not referenced:
            artifact = self.settings.storage_path / "artifacts" / artifact_key
            try:
                if artifact.is_file():
                    artifact.unlink()
            except OSError:
                logger.warning("Could not remove an unreferenced artifact: %s", artifact_key)
        return {"deleted": True, "version_id": version_id, "comparisons": len(comparison_ids)}

    def ensure_comparison(self, session: Session, old: Version, new: Version, mode: str) -> Comparison:
        if old.law_id != new.law_id:
            raise DomainError("Both versions must belong to the same law.")
        law = get(session, Law, old.law_id)
        self.refresh_version_identity(session, law, old)
        self.refresh_version_identity(session, law, new)
        pair = assess_comparison_identity(law, old, new)
        if pair["status"] == "mismatch":
            raise DomainError(
                "These artifacts identify different legal works. Choose the correct version or inspect the saved originals.",
                409,
                "document_identity_mismatch",
            )
        unresolved = [
            (version, pair[side])
            for side, version in (("old", old), ("new", new))
            if pair[side]["status"] == "unknown"
            and not self.identity_confirmed(session, version, pair[side])
        ]
        if unresolved:
            raise DomainError(
                "Document identity is not clear enough to compare automatically. Confirm the unknown artifact assignment or select another version.",
                409,
                "document_identity_unknown",
            )
        existing = session.scalar(
            select(Comparison).where(
                Comparison.old_version_id == old.id,
                Comparison.new_version_id == new.id,
                Comparison.mode == mode,
            )
        )
        if existing:
            self.ensure_complete_diff(session, existing, old, new)
            self.refresh_comparison_identity(session, existing)
            return existing
        overview_started = time.perf_counter()
        diff = compare_passages(old.passages, new.passages)
        diff["metrics"] = {
            "overview_ms": round((time.perf_counter() - overview_started) * 1000, 2),
            "measured_at": utcnow().isoformat(),
        }
        comparison = Comparison(
            owner_organization_id=(
                None
                if old.owner_organization_id is None and new.owner_organization_id is None
                else self.organization_id
            ),
            law_id=old.law_id,
            old_version_id=old.id,
            new_version_id=new.id,
            mode=mode,
            diff=diff,
            identity_json=pair,
        )
        session.add(comparison)
        session.flush()
        return comparison

    @staticmethod
    def ensure_complete_diff(
        session: Session, comparison: Comparison, old: Version, new: Version
    ) -> bool:
        current = comparison.diff or {}
        complete = (
            current.get("schema_version") == DIFF_SCHEMA_VERSION
            and current.get("complete") is True
            and current.get("old_passage_count") == len(old.passages)
            and current.get("new_passage_count") == len(new.passages)
        )
        if complete:
            return False
        overview_started = time.perf_counter()
        comparison.diff = compare_passages(old.passages, new.passages)
        comparison.diff["metrics"] = {
            "overview_ms": round((time.perf_counter() - overview_started) * 1000, 2),
            "measured_at": utcnow().isoformat(),
        }
        session.flush()
        return True

    async def add_source(self, data: dict):
        url = canonical_url(data["url"])
        preview = await self.preview(url, data.get("provider", "native"))
        with self.write_guard, self.db.session() as session:
            if session.scalar(select(Source).where(Source.url == url)):
                raise DomainError("This website is already connected.", 409, "duplicate_source")
            source = Source(
                name=data.get("name") or preview["title"][:250],
                url=url,
                section=data.get("section") or "/",
                provider=data.get("provider", "native"),
                last_checked=utcnow(),
            )
            session.add(source)
            session.commit()
            return {**as_dict(source), "preview": preview}

    async def update_source(self, source_id: str, data: dict):
        with self.db.session() as session:
            values = as_dict(get(session, Source, source_id))
        url = canonical_url(data.get("url") or values["url"])
        provider = data.get("provider", values["provider"])
        preview = await self.preview(url, provider)
        with self.write_guard, self.db.session() as session:
            if session.scalar(select(Source).where(Source.url == url, Source.id != source_id)):
                raise DomainError("This website is already connected.", 409, "duplicate_source")
            source = get(session, Source, source_id)
            source.name = data.get("name") or source.name
            source.url, source.provider = url, provider
            source.section = data.get("section") or source.section
            source.error, source.last_checked = None, utcnow()
            source.discovery = {}
            session.commit()
            return {**as_dict(source), "preview": preview}

    def list_regulatory_works(
        self, *, kind: str | None = None, authority: str | None = None, limit: int = 100
    ) -> list[dict]:
        with self.db.session() as session:
            query = select(RegulatoryWork)
            if kind:
                query = query.where(RegulatoryWork.kind == kind)
            if authority:
                query = query.where(RegulatoryWork.authority == authority.lower())
            works = session.scalars(
                query.order_by(RegulatoryWork.updated_at.desc(), RegulatoryWork.id).limit(limit)
            ).all()
            result = []
            for work in works:
                identifiers = session.scalars(
                    select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id)
                ).all()
                expressions = session.scalars(
                    select(RegulatoryExpression).where(RegulatoryExpression.work_id == work.id)
                ).all()
                result.append(
                    {
                        **as_dict(work),
                        "identifiers": [as_dict(item) for item in identifiers],
                        "languages": sorted({item.language for item in expressions}),
                        "expression_count": len(expressions),
                    }
                )
            return result

    def registry(self, filters: RegistryFilters, user_id: str | None = None) -> dict:
        with self.db.session() as session:
            return RegistryReader(self.organization_id, user_id).page(session, filters)

    def impact_inbox(self, filters: ImpactInboxFilters, user_id: str | None) -> dict:
        with self.db.session() as session:
            return ImpactInboxReader(self.organization_id, user_id).page(session, filters)

    def impact_matrix(self, output_locale: str) -> dict:
        with self.db.session() as session:
            return ImpactMatrixReader(
                profile_id=self.tenant_record_id,
                settings=self.settings,
                prompts=self.prompt_settings,
                output_locale=output_locale,
            ).page(session)

    def digest_overview(self, user_id: str | None) -> dict:
        if not user_id:
            raise DomainError("Sign in to configure digests.", 401, "authentication_required")
        with self.db.session() as session:
            preference = session.scalar(
                select(DigestPreference).where(DigestPreference.user_id == user_id)
            )
            effective = preference or DigestPreference(
                organization_id=self.organization_id,
                user_id=user_id,
                enabled=False,
                frequency="weekly",
                severities=[],
                sources=[],
            )
            period_end = utcnow()
            period_start = period_end - digests.FREQUENCIES[effective.frequency]
            reader = ImpactInboxReader(self.organization_id, user_id)
            groups = reader.iter_groups(
                session, digests.inbox_filters(effective, period_start, period_end)
            )
            deliveries = list(
                session.scalars(
                    select(DigestDelivery)
                    .where(DigestDelivery.user_id == user_id)
                    .order_by(DigestDelivery.created_at.desc())
                    .limit(20)
                )
            )
            source_options = reader.source_options(session)
            return {
                "preference": digests.serialize_preference(preference),
                "preview": digests.summarize_groups(groups, effective, period_start, period_end),
                "source_options": source_options,
                "delivery_mode": self.environment_settings.auth_email_mode,
                "deliveries": [digests.serialize_delivery(item) for item in deliveries],
            }

    def save_digest_preference(
        self,
        user_id: str | None,
        *,
        enabled: bool,
        frequency: str,
        severities: list[str],
        sources: list[str],
    ) -> dict:
        if not user_id:
            raise DomainError("Sign in to configure digests.", 401, "authentication_required")
        if frequency not in digests.FREQUENCIES:
            raise DomainError("Choose a daily or weekly digest.", 422, "digest_frequency_invalid")
        if any(value not in digests.SEVERITIES for value in severities):
            raise DomainError("Choose supported severity filters.", 422, "digest_severity_invalid")
        clean_sources = list(dict.fromkeys(value.strip()[:120] for value in sources if value.strip()))
        with self.write_guard, self.db.session() as session:
            preference = session.scalar(
                select(DigestPreference).where(DigestPreference.user_id == user_id)
            )
            now = utcnow()
            if not preference:
                preference = DigestPreference(user_id=user_id)
                session.add(preference)
            schedule_changed = preference.frequency != frequency or not preference.enabled
            preference.enabled = enabled
            preference.frequency = frequency
            preference.severities = list(dict.fromkeys(severities))
            preference.sources = clean_sources[:20]
            preference.next_delivery_at = (
                digests.next_delivery(now, frequency)
                if enabled and (schedule_changed or preference.next_delivery_at is None)
                else preference.next_delivery_at if enabled else None
            )
            preference.updated_at = now
            session.commit()
        return self.digest_overview(user_id)

    def enqueue_digest_now(self, user_id: str | None) -> dict:
        if not user_id:
            raise DomainError("Sign in to send a digest.", 401, "authentication_required")
        with self.write_guard, self.db.session() as session:
            preference = session.scalar(
                select(DigestPreference).where(DigestPreference.user_id == user_id)
            )
            if not preference or not preference.enabled:
                raise DomainError("Enable the digest before sending it.", 409, "digest_not_enabled")
            period_end = utcnow()
            period_start = preference.last_sent_at or (
                period_end - digests.FREQUENCIES[preference.frequency]
            )
            delivery = DigestDelivery(
                user_id=user_id,
                preference_id=preference.id,
                frequency=preference.frequency,
                period_start=period_start,
                period_end=period_end,
            )
            session.add(delivery)
            session.flush()
            job, _ = durable_jobs.enqueue(
                session,
                job_type="digest_delivery",
                target_type="digest_delivery",
                target_id=delivery.id,
                queue="maintenance",
                priority=2,
                idempotency_key=f"digest:{preference.id}:{period_end.isoformat()}",
                payload={"delivery_id": delivery.id},
                max_attempts=self.settings.job_max_attempts,
                steps=[("Build saved impact summary", {}), ("Deliver opted-in email", {})],
            )
            session.commit()
            return durable_jobs.serialize(session, job)

    def unsubscribe_digest(self, token: str) -> dict:
        preference_id = digests.preference_id_from_token(self.environment_settings, token)
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            preference = session.get(DigestPreference, preference_id)
            if not preference:
                raise DomainError("This unsubscribe link is invalid.", 422, "digest_token_invalid")
            preference.enabled = False
            preference.next_delivery_at = None
            preference.updated_at = utcnow()
            session.commit()
            return {"unsubscribed": True}

    def set_impact_inbox_state(
        self, event_id: str, state: str, user_id: str | None
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return ImpactInboxReader(self.organization_id, user_id).set_state(
                session, event_id, state
            )

    def regulatory_relation_detail(self, relation_id: str) -> dict:
        with self.db.session() as session:
            relation = get(session, RegulatoryRelation, relation_id)
            visible = session.scalar(
                select(OrganizationRelationCandidate.id)
                .join(
                    RelationCandidate,
                    RelationCandidate.id == OrganizationRelationCandidate.candidate_id,
                )
                .where(RelationCandidate.relation_id == relation_id)
                .limit(1)
            )
            if not visible:
                raise DomainError("The requested relation was not found.", 404, "not_found")
            subject = get(session, RegulatoryWork, relation.subject_work_id)
            object_work = get(session, RegulatoryWork, relation.object_work_id)
            return {
                **as_dict(relation),
                "subject": {"id": subject.id, "title": subject.title},
                "object": {"id": object_work.id, "title": object_work.title},
            }

    def review_relation_candidate(
        self,
        organization_candidate_id: str,
        decision: str,
        note: str,
        actor_user_id: str | None,
        *,
        workflow_variant: str = "inbox_list_v1",
        review_duration_ms: int | None = None,
        evidence_opened: bool = False,
    ) -> dict:
        if decision not in {"confirmed", "rejected", "annotated"}:
            raise DomainError(
                "Choose confirmed, rejected, or annotated.",
                422,
                "invalid_relation_review",
            )
        note = note.strip()
        if len(note) < 3:
            raise DomainError(
                "Add a short review reason or annotation.",
                422,
                "relation_review_note_required",
            )
        with self.write_guard, self.db.session() as session:
            delivery = get(session, OrganizationRelationCandidate, organization_candidate_id)
            candidate = get(session, RelationCandidate, delivery.candidate_id)
            official = (
                session.get(RegulatoryRelation, candidate.relation_id)
                if candidate.relation_id
                else None
            )
            if official and official.state == "confirmed":
                raise DomainError(
                    "Confirmed official metadata cannot be replaced by an organization review.",
                    409,
                    "official_relation_authoritative",
                )
            review = OrganizationRelationReview(
                organization_candidate_id=delivery.id,
                decision=decision,
                note=note,
                workflow_variant=workflow_variant,
                review_duration_ms=review_duration_ms,
                evidence_opened=evidence_opened,
                actor_user_id=actor_user_id,
            )
            session.add(review)
            session.commit()
            return as_dict(review)

    def relation_review_history(self, organization_candidate_id: str) -> dict:
        with self.db.session() as session:
            delivery = get(session, OrganizationRelationCandidate, organization_candidate_id)
            reviews = list(
                session.scalars(
                    select(OrganizationRelationReview)
                    .where(
                        OrganizationRelationReview.organization_candidate_id == delivery.id
                    )
                    .order_by(
                        OrganizationRelationReview.created_at.desc(),
                        OrganizationRelationReview.id.desc(),
                    )
                )
            )
            actors = {
                review.actor_user_id: session.get(User, review.actor_user_id)
                for review in reviews
                if review.actor_user_id
            }
            return {
                "items": [
                    {
                        **as_dict(review),
                        "actor": (
                            {
                                "id": actor.id,
                                "name": actor.name,
                            }
                            if (actor := actors.get(review.actor_user_id))
                            else None
                        ),
                    }
                    for review in reviews
                ],
                "total": len(reviews),
            }

    async def monitor_relation_successor(self, organization_candidate_id: str) -> dict:
        with self.db.session() as session:
            delivery = get(session, OrganizationRelationCandidate, organization_candidate_id)
            candidate = get(session, RelationCandidate, delivery.candidate_id)
            relation = (
                session.get(RegulatoryRelation, candidate.relation_id)
                if candidate.relation_id
                else None
            )
            if not relation or relation.state != "confirmed" or relation.relation_type != "replaces":
                raise DomainError(
                    "Only a confirmed official replacement can add a successor.",
                    409,
                    "successor_not_confirmed",
                )
            successor = get(session, RegulatoryWork, relation.subject_work_id)
            mapping = session.scalar(
                select(LegacyDocumentMapping).where(
                    LegacyDocumentMapping.work_id == successor.id
                )
            )
            law = session.get(Law, mapping.law_id) if mapping else None
            existing_watch = (
                session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law.id))
                if law
                else None
            )
            if existing_watch:
                existing_watch.active = True
                existing_watch.display_name = successor.title or existing_watch.display_name
                session.commit()
                return self.law_summary(session, law, existing_watch)
            if law:
                watch = DocumentWatch(
                    law_id=law.id,
                    display_name=successor.title or law.name,
                    active=True,
                    last_result="successor_added",
                )
                session.add(watch)
                session.commit()
                return self.law_summary(session, law, watch)
            url = successor.stable_official_url
            title = successor.title
        if not url:
            raise DomainError(
                "The confirmed successor has no official URL to monitor.",
                409,
                "successor_url_missing",
            )
        return await self.add_law({"url": url, "name": title, "provider": "native"})

    def mark_registry_event_read(
        self, event_id: str, read: bool, user_id: str | None = None
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return RegistryReader(self.organization_id, user_id).mark_read(
                session, event_id, read
            )

    def regulatory_timeline(self, law_id: str) -> dict:
        with self.db.session() as session:
            return RegistryReader(self.organization_id).timeline(session, law_id)

    def connector_statuses(self) -> list[dict]:
        saved = self.connector_runner.statuses()
        known = {item["connector"] for item in saved}
        for contract in OFFICIAL_SOURCE_CONTRACTS:
            if contract.manifest.name in known:
                continue
            saved.append(
                {
                    "connector": contract.manifest.name,
                    "stream": "default",
                    "health": "unknown",
                    "message": "No synchronization or source-contract probe has been persisted yet.",
                    "contract_version": CONNECTOR_CONTRACT_VERSION,
                    "connector_version": contract.manifest.connector_version,
                    "schema_version": contract.manifest.schema_version,
                    "cursor": None,
                    "checkpoint": {},
                    "source_contract": contract.manifest.source_contract,
                    "last_started_at": None,
                    "last_completed_at": None,
                    "last_success_at": None,
                }
            )
        return sorted(saved, key=lambda item: (item["connector"], item["stream"]))

    def connector_capabilities(self) -> dict:
        return capability_catalogue()

    def source_pack_catalogue(self) -> dict:
        with self.db.session(include_all_organizations=True) as session:
            schedules = synchronization.schedule_status(session, self.settings)["items"]
            session.commit()
        with self.db.session() as session:
            return source_packs.catalogue(session, schedules)

    def activate_source_pack(self, pack_id: str, actor_user_id: str | None) -> dict:
        with self.write_guard, self.db.session() as session:
            return source_packs.activate(
                session,
                pack_id,
                organization_id=self.organization_id,
                actor_user_id=actor_user_id,
            )

    def deactivate_source_pack(self, pack_id: str) -> dict:
        with self.write_guard, self.db.session() as session:
            return source_packs.deactivate(session, pack_id)

    def request_source_pack_change(
        self, pack_id: str, action: str, requested_by_user_id: str | None
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return source_packs.request_change(
                session,
                pack_id,
                action,
                requested_by_user_id=requested_by_user_id,
            )

    def monitoring_topics(self, *, include_archived: bool = False) -> list[dict]:
        with self.db.session() as session:
            return monitoring_topics.list_topics(session, include_archived=include_archived)

    def monitoring_topic(self, topic_id: str) -> dict:
        with self.db.session() as session:
            return monitoring_topics.get_topic(session, topic_id)

    def request_topic_history_scan(self, topic_id: str) -> dict:
        with self.write_guard, self.db.session() as session:
            return monitoring_topics.request_history_scan(session, topic_id)

    def monitoring_topic_matches(self, topic_id: str, *, limit: int = 100) -> list[dict]:
        with self.db.session() as session:
            return topic_matching.list_matches(session, topic_id, limit=limit)

    def preview_monitoring_topic(self, data: dict) -> dict:
        with self.db.session() as session:
            return monitoring_topics.preview(session, data)

    async def draft_monitoring_topic(
        self, goal: str, locale: str, *, actor_user_id: str | None
    ) -> dict:
        """Ask the configured model for a proposal without activating monitoring."""
        with self.db.session() as session:
            context = monitoring_topics.draft_context(session)
        schema = monitoring_topics.TopicDraftOutput.model_json_schema()
        system = (
            "Create a conservative monitoring-topic plan from the user's goal. "
            "Return only JSON matching the schema. Select only values and source-pack IDs "
            "listed in the supplied context. Do not broaden the goal or invent sources. "
            "The user will inspect, edit, preview, and explicitly confirm this draft."
        )
        payload = {
            "task": "monitoring_topic_draft",
            "goal": goal,
            "output_locale": locale,
            "allowed": context,
            "defaults": {
                "jurisdictions": ["CH"],
                "importance_floor": "low",
            },
        }

        def parse_and_validate(candidate: str) -> dict:
            parsed = monitoring_topics.parse_draft(candidate)
            with self.db.session() as validation_session:
                return monitoring_topics.normalize_plan(parsed.model_dump(), validation_session)

        raw = await self.model_client.complete(
            system,
            json.dumps(payload, ensure_ascii=False),
            response_schema=schema,
        )
        try:
            proposed = parse_and_validate(raw)
        except DomainError as original_error:
            repair_payload = {
                "task": "repair_monitoring_topic_draft",
                "invalid_response": raw[:12000],
                "allowed": context,
                "schema": schema,
            }
            repaired = await self.model_client.complete(
                "Repair the candidate. Return only valid JSON matching the supplied schema and allowed values.",
                json.dumps(repair_payload, ensure_ascii=False),
                response_schema=schema,
            )
            try:
                proposed = parse_and_validate(repaired)
            except DomainError:
                raise original_error from None
        with self.write_guard, self.db.session() as session:
            return monitoring_topics.save_draft(
                session,
                goal=goal,
                plan=proposed,
                provider=self.settings.apertus_provider,
                model=self.settings.apertus_model,
                prompt_revision=self.prompt_revision,
                actor_user_id=actor_user_id,
            )

    def create_monitoring_topic(
        self,
        data: dict,
        *,
        idempotency_key: str,
        actor_user_id: str | None,
        ai_draft_id: str | None = None,
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return monitoring_topics.create_topic(
                session,
                data,
                idempotency_key=idempotency_key,
                actor_user_id=actor_user_id,
                ai_draft_id=ai_draft_id,
            )

    def update_monitoring_topic(
        self,
        topic_id: str,
        data: dict,
        *,
        expected_revision: int,
        actor_user_id: str | None,
        ai_draft_id: str | None = None,
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return monitoring_topics.update_topic(
                session,
                topic_id,
                data,
                expected_revision=expected_revision,
                actor_user_id=actor_user_id,
                ai_draft_id=ai_draft_id,
            )

    def change_monitoring_topic_status(
        self,
        topic_id: str,
        status: str,
        *,
        expected_revision: int,
        actor_user_id: str | None,
    ) -> dict:
        with self.write_guard, self.db.session() as session:
            return monitoring_topics.change_status(
                session,
                topic_id,
                status,
                expected_revision=expected_revision,
                actor_user_id=actor_user_id,
            )

    async def sync_fedlex(self, stream: str) -> dict:
        connector = next(
            (
                item
                for item in fedlex_connectors(self.settings, self.integration_logger)
                if item.stream == stream
            ),
            None,
        )
        if connector is None:
            raise DomainError(
                "Choose a supported Fedlex stream.",
                422,
                "fedlex_stream_invalid",
            )
        result = await self.connector_runner.run_page(connector, stream=stream)
        return {
            "connector": result.connector,
            "stream": result.stream,
            "status": result.status,
            "page_id": result.page_id,
            "persisted": result.persisted,
            "total": result.total,
            "next_cursor": result.next_cursor,
            "error": result.error,
        }

    async def sync_broad_official(self, connector_name: str, stream: str) -> dict:
        available = (
            federal_news_connectors(self.settings, self.integration_logger)
            if connector_name == "federal-news"
            else finma_news_connectors(self.settings, self.integration_logger)
            if connector_name == "finma-news"
            else ()
        )
        connector = next((item for item in available if item.stream == stream), None)
        if connector is None:
            raise DomainError(
                "Choose a supported official-news stream.", 422, "official_news_stream_invalid"
            )
        result = await self.connector_runner.run_page(connector, stream=stream)
        return {
            "connector": result.connector,
            "stream": result.stream,
            "status": result.status,
            "page_id": result.page_id,
            "persisted": result.persisted,
            "total": result.total,
            "next_cursor": result.next_cursor,
            "error": result.error,
        }

    async def sync_parliament(self, stream: str) -> dict:
        active_ids = ()
        if stream == "active":
            with self.db.session(include_all_organizations=True) as session:
                works = session.scalars(
                    select(RegulatoryWork).where(
                        RegulatoryWork.authority == "swiss_parliament"
                    )
                ).all()
                active_work_ids = {
                    work.id
                    for work in works
                    if not bool((work.metadata_json or {}).get("is_final"))
                }
                identifiers = (
                    session.scalars(
                        select(RegulatoryIdentifier).where(
                            RegulatoryIdentifier.work_id.in_(active_work_ids),
                            RegulatoryIdentifier.scheme == "parliament_affair_id",
                        )
                    ).all()
                    if active_work_ids
                    else []
                )
                active_ids = tuple(
                    item.normalized_value
                    for item in identifiers
                    if item.normalized_value.isdigit()
                )
        connector = (
            ParliamentNoticeConnector(self.settings, self.integration_logger)
            if stream == "notices"
            else next(
                (
                    item
                    for item in parliament_connectors(
                        self.settings,
                        self.integration_logger,
                        active_ids=active_ids,
                    )
                    if item.stream == stream
                ),
                None,
            )
        )
        if connector is None:
            raise DomainError(
                "Choose a supported Swiss Parliament stream.",
                422,
                "parliament_stream_invalid",
            )
        result = await self.connector_runner.run_page(connector, stream=stream)
        return {
            "connector": result.connector,
            "stream": result.stream,
            "status": result.status,
            "page_id": result.page_id,
            "persisted": result.persisted,
            "total": result.total,
            "next_cursor": result.next_cursor,
            "error": result.error,
        }

    async def sync_federal_court(self, stream: str) -> dict:
        connector = next(
            (
                item
                for item in federal_court_connectors(
                    self.settings,
                    self.integration_logger,
                )
                if item.mode == stream
            ),
            None,
        )
        if connector is None:
            raise DomainError(
                "Choose a supported Swiss Federal Supreme Court stream.",
                422,
                "federal_court_stream_invalid",
            )
        result = await self.connector_runner.run_page(connector, stream=stream)
        return {
            "connector": result.connector,
            "stream": result.stream,
            "status": result.status,
            "page_id": result.page_id,
            "persisted": result.persisted,
            "total": result.total,
            "next_cursor": result.next_cursor,
            "error": result.error,
        }

    async def sync_federal_criminal_court(self, stream: str) -> dict:
        connector = next(
            (
                item
                for item in federal_criminal_court_connectors(
                    self.settings,
                    self.integration_logger,
                )
                if stream == "latest"
            ),
            None,
        )
        if connector is None:
            raise DomainError(
                "Choose the supported Swiss Federal Criminal Court stream.",
                422,
                "federal_criminal_court_stream_invalid",
            )
        result = await self.connector_runner.run_page(connector, stream=stream)
        return {
            "connector": result.connector,
            "stream": result.stream,
            "status": result.status,
            "page_id": result.page_id,
            "persisted": result.persisted,
            "total": result.total,
            "next_cursor": result.next_cursor,
            "error": result.error,
        }

    def connector_schedule_status(self) -> dict:
        with self.db.session(include_all_organizations=True) as session:
            result = synchronization.schedule_status(session, self.settings)
            session.commit()
            return result

    def update_connector_schedule(
        self,
        connector: str,
        stream: str,
        *,
        enabled: bool,
        interval_seconds: int,
        jitter_seconds: int,
        window_start: str | None,
        window_end: str | None,
    ) -> dict:
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            schedule = synchronization.update_schedule(
                session,
                connector,
                stream,
                enabled=enabled,
                interval_seconds=interval_seconds,
                jitter_seconds=jitter_seconds,
                window_start=window_start,
                window_end=window_end,
            )
            session.commit()
            return synchronization.serialize_schedule(session, schedule)

    def enqueue_connector_sync(self, connector: str, stream: str) -> dict:
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            try:
                job, run, reused = synchronization.enqueue_manual(
                    session,
                    self.settings,
                    connector,
                    stream,
                    self.organization_id,
                )
            except DomainError as exc:
                if exc.code != "connector_schedule_invalid":
                    raise
                codes = {
                    "fedlex": "fedlex_stream_invalid",
                    "swiss-parliament": "parliament_stream_invalid",
                    "federal-supreme-court": "federal_court_stream_invalid",
                    "federal-criminal-court": "federal_criminal_court_stream_invalid",
                }
                raise DomainError(exc.message, exc.status, codes.get(connector, exc.code)) from exc
            session.commit()
            return {
                "reused": reused,
                "run": synchronization.serialize_run(run),
                "job": durable_jobs.serialize(session, job),
            }

    async def _run_connector_job(self, run_id: str, connector: str, stream: str) -> dict:
        enrich_correlation(connector_run_id=run_id)
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            synchronization.start_run(session, run_id)
            session.commit()
        if connector == "fedlex":
            result = await self.sync_fedlex(stream)
        elif connector == "swiss-parliament":
            result = await self.sync_parliament(stream)
        elif connector == "federal-supreme-court":
            result = await self.sync_federal_court(stream)
        elif connector == "federal-criminal-court":
            result = await self.sync_federal_criminal_court(stream)
        elif connector in {"federal-news", "finma-news"}:
            result = await self.sync_broad_official(connector, stream)
        else:
            raise DomainError(
                "This scheduled connector is not supported.",
                422,
                "connector_schedule_invalid",
            )
        with self.write_guard, self.db.session(include_all_organizations=True) as session:
            run = synchronization.finish_run(
                session, run_id, result, settings=self.settings
            )
            relation_deliveries = synchronization.relation_delivery_refs_for_run(session, run)
            session.commit()
            serialized_run = synchronization.serialize_run(run)
        relation_jobs = await self.enqueue_pending_relation_analyses(relation_deliveries)
        return {
            **result,
            "run": serialized_run,
            "relation_analysis_jobs": relation_jobs,
        }

    def regulatory_work_detail(self, work_id: str) -> dict:
        with self.db.session() as session:
            work = get(session, RegulatoryWork, work_id)
            identifiers = session.scalars(
                select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id)
            ).all()
            expressions = session.scalars(
                select(RegulatoryExpression).where(RegulatoryExpression.work_id == work.id)
            ).all()
            expression_ids = [item.id for item in expressions]
            versions = (
                session.scalars(
                    select(RegulatoryDocumentVersion).where(
                        RegulatoryDocumentVersion.expression_id.in_(expression_ids)
                    )
                ).all()
                if expression_ids
                else []
            )
            entity_ids = [work.id, *expression_ids, *(item.id for item in versions)]
            dates = session.scalars(
                select(RegulatoryDate).where(RegulatoryDate.entity_id.in_(entity_ids))
            ).all()
            events = session.scalars(
                select(RegulatoryEvent)
                .where(RegulatoryEvent.work_id == work.id)
                .order_by(RegulatoryEvent.detected_at.desc())
            ).all()
            relations = session.scalars(
                select(RegulatoryRelation)
                .where(
                    or_(
                        RegulatoryRelation.subject_work_id == work.id,
                        RegulatoryRelation.object_work_id == work.id,
                    )
                )
                .order_by(RegulatoryRelation.created_at.desc())
            ).all()
            mappings = session.scalars(
                select(LegacyDocumentMapping).where(LegacyDocumentMapping.work_id == work.id)
            ).all()
            return {
                **as_dict(work),
                "identifiers": [as_dict(item) for item in identifiers],
                "expressions": [as_dict(item) for item in expressions],
                "versions": [as_dict(item) for item in versions],
                "dates": [as_dict(item) for item in dates],
                "events": [as_dict(item) for item in events],
                "relations": [as_dict(item) for item in relations],
                "legacy_mappings": [as_dict(item) for item in mappings],
            }

    def delete_source(self, source_id: str):
        with self.write_guard, self.db.session() as session:
            source = get(session, Source, source_id)
            detached = list(session.scalars(select(Law).where(Law.source_id == source_id)))
            for law in detached:
                law.source_id = None
            name = source.name
            session.delete(source)
            session.commit()
            return {"deleted": True, "name": name, "detached_documents": len(detached)}

    async def discover(self, source_id: str):
        with self.db.session() as session:
            source = get(session, Source, source_id)
            url, provider, section = source.url, source.provider, source.section
        try:
            fetched = await self.fetcher.fetch(url, provider)
            result = discover_links(fetched, section)
            semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)
            for candidate in result["candidates"]:
                candidate.update(inspected=False, status="pending", preview=None, error=None)

            async def inspect_candidate(candidate):
                async with semaphore:
                    candidate["inspected"] = True
                    candidate["status"] = "inspecting"
                    try:
                        preview = await self.preview(
                            candidate["url"], provider, boundary=(fetched.url, section)
                        )
                        candidate.update(
                            title=preview["title"],
                            content_type=preview["content_type"],
                            preview=preview,
                            verified=True,
                            status="verified",
                        )
                    except DomainError as exc:
                        candidate.update(status="failed", error=exc.message, error_code=exc.code)

            timed_out = False
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(inspect_candidate(c) for c in result["candidates"])),
                    timeout=DISCOVERY_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                timed_out = True
            for candidate in result["candidates"]:
                if candidate["status"] in {"pending", "inspecting"}:
                    candidate.update(
                        status="failed" if candidate["inspected"] else "not_inspected",
                        error="The discovery time limit was reached. Preview this document separately to retry.",
                        error_code="discovery_time_limit",
                    )
            result.update(
                inspected_count=sum(c["inspected"] for c in result["candidates"]),
                verified_count=sum(c["verified"] for c in result["candidates"]),
                error_count=sum(c["status"] == "failed" for c in result["candidates"]),
                uninspected_count=sum(not c["inspected"] for c in result["candidates"]),
                time_limit_seconds=DISCOVERY_TIMEOUT_SECONDS,
                time_limit_reached=timed_out,
                note="One listing page and at most 50 direct documents in the selected section. Each result shows its real extraction outcome. No deeper links are followed; this is not exhaustive site coverage or evidence of an amendment.",
            )
        except DomainError as exc:
            with self.write_guard, self.db.session() as session:
                source = get(session, Source, source_id)
                source.error, source.last_checked = exc.message, utcnow()
                session.commit()
            raise
        with self.write_guard, self.db.session() as session:
            source = get(session, Source, source_id)
            tracked = set(
                session.scalars(
                    select(Law.url).join(DocumentWatch, DocumentWatch.law_id == Law.id)
                )
            )
            for candidate in result["candidates"]:
                candidate["tracked"] = candidate["url"] in tracked
            source.discovery, source.last_checked, source.error = result, utcnow(), None
            session.commit()
        return result

    async def add_law(self, data: dict):
        url = canonical_url(data["url"])
        provider = data.get("provider", "native")
        shared_official = self.is_shared_official_url(url) and not data.get("synthetic", False)
        canonical_identity = self.canonical_document_identity(url)
        with self.db.session() as session:
            existing = session.scalar(
                select(Law).where(
                    Law.canonical_identity == canonical_identity,
                    Law.owner_organization_id.is_(None)
                    if shared_official
                    else Law.owner_organization_id == self.organization_id,
                )
            )
            if existing and self.watch(session, existing.id, required=False):
                raise DomainError(
                    f"This document is already tracked as '{existing.name}'.", 409, "duplicate_law"
                )
            if data.get("source_id"):
                get(session, Source, data["source_id"])
            if existing:
                watch = DocumentWatch(
                    law_id=existing.id,
                    display_name=data.get("name") or existing.name,
                    active=True,
                    last_result="baseline_reused",
                )
                session.add(watch)
                session.commit()
                return self.law_summary(session, existing, watch)
        fetched = await self.fetcher.fetch(url, provider)
        name = PurePosixPath(urlsplit(fetched.url).path).name or "document.html"
        document = await asyncio.to_thread(extract, fetched.body, fetched.content_type, name, provider)
        with self.write_guard, self.db.session() as session:
            if session.scalar(
                select(Law.id).where(
                    Law.canonical_identity == canonical_identity,
                    Law.owner_organization_id.is_(None)
                    if shared_official
                    else Law.owner_organization_id == self.organization_id,
                )
            ):
                raise DomainError("This document was already added.", 409, "duplicate_law")
            law = Law(
                owner_organization_id=None if shared_official else self.organization_id,
                canonical_identity=canonical_identity,
                name=data.get("name") or document.title[:300],
                url=url,
                source_id=None if shared_official else data.get("source_id"),
                provider=provider,
                last_checked=utcnow(),
            )
            session.add(law)
            session.flush()
            version, _ = self.save_snapshot(
                session,
                law,
                document,
                "live",
                fetched.url,
                synthetic=data.get("synthetic", False),
                metadata=fetched.metadata,
            )
            law.current_version_id = version.id
            self.regulatory_corpus.map_legacy_document(session, law, version)
            watch = DocumentWatch(
                law_id=law.id,
                display_name=data.get("name") or law.name,
                active=True,
                last_checked=utcnow(),
            )
            session.add(watch)
            session.commit()
            return self.law_summary(session, law, watch)

    def list_laws(self):
        with self.db.session() as session:
            watches = list(
                session.scalars(select(DocumentWatch).order_by(DocumentWatch.created_at.desc()))
            )
            return [self.law_summary(session, get(session, Law, watch.law_id), watch) for watch in watches]

    def law_summary(self, session: Session, law: Law, watch: DocumentWatch | None = None):
        watch = watch or self.watch(session, law.id)
        current = session.get(Version, law.current_version_id) if law.current_version_id else None
        last_item = session.scalar(
            select(ScanItem)
            .where(
                ScanItem.law_id == law.id,
                ScanItem.comparison_id.is_not(None),
            )
            .order_by(ScanItem.created_at.desc())
            .limit(1)
        )
        comparison = (
            session.get(Comparison, last_item.comparison_id)
            if last_item
            else session.scalar(
                select(Comparison)
                .where(Comparison.law_id == law.id)
                .order_by(Comparison.created_at.desc())
                .limit(1)
            )
        )
        analysis = self.latest_analysis(session, comparison) if comparison else None
        return {
            **as_dict(law, {"owner_organization_id"}),
            "name": watch.display_name,
            "active": watch.active,
            "last_checked": as_dict(watch)["last_checked"],
            "last_result": watch.last_result,
            "last_error": watch.last_error,
            "watch_id": watch.id,
            "selected_baseline_version_id": watch.selected_baseline_version_id,
            "corpus_scope": "shared_public" if law.owner_organization_id is None else "organization_private",
            "current_version": version_summary(current) if current else None,
            "comparison_id": comparison.id if comparison else None,
            "comparison_mode": comparison.mode if comparison else None,
            "change_counts": comparison.diff["counts"] if comparison else None,
            "analysis": analysis,
        }

    def law_detail(self, law_id: str):
        with self.db.session() as session:
            law = get(session, Law, law_id)
            watch = self.watch(session, law_id, required=False)
            if watch is None:
                raise DomainError("The requested record was not found.", 404, "not_found")
            return {
                **self.law_summary(session, law, watch),
                "regulatory_timeline": RegistryReader(self.organization_id).timeline(session, law_id),
                "versions": [
                    version_summary(v)
                    for v in session.scalars(
                        select(Version).where(Version.law_id == law_id).order_by(Version.created_at.desc())
                    )
                ],
                "observations": [
                    as_dict(o, {"artifact_key"})
                    for o in session.scalars(
                        select(Observation)
                        .where(Observation.law_id == law_id)
                        .order_by(Observation.created_at.desc())
                        .limit(100)
                    )
                ],
                "comparisons": [
                    as_dict(c, {"diff"}) | {"counts": c.diff["counts"]}
                    for c in session.scalars(
                        select(Comparison)
                        .where(Comparison.law_id == law_id)
                        .order_by(Comparison.created_at.desc())
                        .limit(50)
                    )
                ],
            }

    def delete_law(self, law_id: str):
        artifact_keys: set[str] = set()
        comparison_ids: list[str] = []
        with self.write_guard, self.db.session() as session:
            law = get(session, Law, law_id)
            watch = self.watch(session, law_id)
            busy = session.scalar(
                select(ScanItem.id)
                .join(Scan)
                .where(ScanItem.law_id == law_id, Scan.status.in_(["queued", "running"]))
                .limit(1)
            )
            if busy:
                raise DomainError(
                    "This document has a scan in progress. Wait for it to finish before deleting it.",
                    409,
                    "scan_in_progress",
                )
            if law.owner_organization_id is None:
                name = watch.display_name
                session.delete(watch)
                session.commit()
                return {
                    "deleted": True,
                    "name": name,
                    "watch_removed": True,
                    "shared_corpus_retained": True,
                    "versions": 0,
                    "comparisons": 0,
                    "scan_entries": 0,
                    "artifacts": 0,
                }
            versions = list(session.scalars(select(Version).where(Version.law_id == law_id)))
            observations = list(
                session.scalars(select(Observation).where(Observation.law_id == law_id))
            )
            comparisons = list(
                session.scalars(select(Comparison).where(Comparison.law_id == law_id))
            )
            scan_items = list(session.scalars(select(ScanItem).where(ScanItem.law_id == law_id)))
            artifact_keys.update(version.artifact_key for version in versions)
            artifact_keys.update(observation.artifact_key for observation in observations)
            comparison_ids = [comparison.id for comparison in comparisons]
            scan_ids = {item.scan_id for item in scan_items}
            job_conditions = []
            if scan_ids:
                job_conditions.append((Job.target_type == "scan") & Job.target_id.in_(scan_ids))
            if comparison_ids:
                job_conditions.append(
                    (Job.target_type == "comparison") & Job.target_id.in_(comparison_ids)
                )
            job_ids = (
                list(session.scalars(select(Job.id).where(or_(*job_conditions))))
                if job_conditions
                else []
            )
            if job_ids:
                active_job = session.scalar(
                    select(Job.id)
                    .where(
                        Job.id.in_(job_ids),
                        Job.state.not_in(durable_jobs.TERMINAL_STATES),
                    )
                    .limit(1)
                )
                if active_job:
                    raise DomainError(
                        "This document still has background work in progress. Cancel it or wait for completion before deleting the document.",
                        409,
                        "job_in_progress",
                    )
            if comparison_ids:
                session.execute(
                    delete(AskRecord).where(AskRecord.comparison_id.in_(comparison_ids))
                )
                session.execute(delete(Analysis).where(Analysis.comparison_id.in_(comparison_ids)))
            if job_ids:
                session.execute(delete(OutboxMessage).where(OutboxMessage.job_id.in_(job_ids)))
                session.execute(delete(JobStep).where(JobStep.job_id.in_(job_ids)))
                session.execute(delete(Job).where(Job.id.in_(job_ids)))
            session.execute(delete(ScanItem).where(ScanItem.law_id == law_id))
            session.execute(delete(IdentityDecision).where(IdentityDecision.law_id == law_id))
            session.execute(delete(Comparison).where(Comparison.law_id == law_id))
            session.execute(delete(Observation).where(Observation.law_id == law_id))
            session.execute(delete(Version).where(Version.law_id == law_id))
            name = law.name
            session.delete(watch)
            session.delete(law)
            for scan_id in scan_ids:
                scan = session.get(Scan, scan_id)
                if not scan:
                    continue
                remaining = session.scalar(
                    select(func.count()).select_from(ScanItem).where(ScanItem.scan_id == scan_id)
                )
                if remaining:
                    scan.total = remaining
                else:
                    session.delete(scan)
            session.commit()
        for comparison_id in comparison_ids:
            self.analysis_locks.pop(comparison_id, None)
            for lock_key in [key for key in self.ask_locks if key.startswith(comparison_id + ":")]:
                self.ask_locks.pop(lock_key, None)
        with self.db.session() as session:
            referenced = set(
                session.scalars(
                    select(Version.artifact_key).where(Version.artifact_key.in_(artifact_keys))
                )
            )
            referenced.update(
                session.scalars(
                    select(Observation.artifact_key).where(
                        Observation.artifact_key.in_(artifact_keys)
                    )
                )
            )
        removed_artifacts = 0
        for artifact_key in artifact_keys - referenced:
            try:
                artifact = self.settings.storage_path / "artifacts" / artifact_key
                if artifact.is_file():
                    artifact.unlink()
                    removed_artifacts += 1
            except OSError:
                logger.warning("Could not remove an unreferenced artifact: %s", artifact_key)
        return {
            "deleted": True,
            "name": name,
            "versions": len(versions),
            "comparisons": len(comparisons),
            "scan_entries": len(scan_items),
            "artifacts": removed_artifacts,
        }

    async def import_version(
        self,
        law_id: str,
        *,
        body: bytes | None,
        filename: str,
        text: str,
        url: str,
        declared_date: str | None,
        synthetic: bool,
        preview: bool,
        allow_identity_mismatch: bool = False,
        confirm_identity: bool = False,
    ):
        with self.db.session() as session:
            law = get(session, Law, law_id)
            law_identity = {"name": law.name, "url": law.url}
        count = int(body is not None) + int(bool(text.strip())) + int(bool(url.strip()))
        if count != 1:
            raise DomainError("Provide exactly one input: file, pasted text, or historical URL.")
        source_url, metadata = None, {}
        if url.strip():
            fetched = await self.fetcher.fetch(canonical_url(url))
            body, mime, source_url, metadata = (
                fetched.body,
                fetched.content_type,
                fetched.url,
                fetched.metadata,
            )
            filename = PurePosixPath(urlsplit(source_url).path).name or "historical-document.html"
            origin = "historical_url"
        elif text.strip():
            body, mime, filename, origin = text.encode("utf-8"), "text/plain", "pasted-version.txt", "pasted"
        else:
            mime, origin = "", "uploaded"
        if body is None or len(body) > self.settings.max_document_bytes:
            raise DomainError("The import exceeds the configured document limit.", 413)
        document = await asyncio.to_thread(extract, body, mime, filename)
        identity = assess_document_identity(
            law_name=law_identity["name"],
            law_url=law_identity["url"],
            title=document.title,
            source_url=source_url,
            passages=document.passages,
            metadata=metadata,
            extractor=document.extractor,
            content_type=document.content_type,
            filename=document.filename,
            declared_date=declared_date,
        )
        if preview:
            return {**document.preview(), "identity": identity}
        if identity["status"] == "mismatch" and not allow_identity_mismatch:
            raise DomainError(
                "This file appears to be a different legal document. You may save it for inspection, but AI comparison and analysis will remain blocked until the correct version is attached.",
                409,
                "document_identity_mismatch",
            )
        if identity["status"] == "unknown" and not confirm_identity:
            raise DomainError(
                "This artifact has no stable official identity. Review the preview and explicitly confirm its assignment before saving it.",
                409,
                "document_identity_unknown",
            )
        with self.write_guard, self.db.session() as session:
            law = get(session, Law, law_id)
            version, reused = self.save_snapshot(
                session, law, document, origin, source_url, declared_date or None, synthetic, metadata
            )
            identity = self.refresh_version_identity(session, law, version)
            if identity["status"] == "unknown" and confirm_identity:
                self.record_identity_decision(
                    session, law, version, identity, "confirm_assignment", "Confirmed during import"
                )
            elif identity["status"] == "mismatch":
                self.record_identity_decision(
                    session, law, version, identity, "saved_for_inspection", "Saved during import"
                )
            session.commit()
            return {
                "version": version_summary(version),
                "reused": reused,
                "current_version_id": law.current_version_id,
                "identity": identity,
            }

    def latest_analysis(
        self,
        session: Session,
        comparison: Comparison,
        output_locale: str = ai.DEFAULT_OUTPUT_LOCALE,
    ):
        attempts = list(
            session.scalars(
                select(Analysis)
                .where(Analysis.comparison_id == comparison.id)
                .order_by(Analysis.created_at.desc())
                .limit(50)
            )
        )
        if not attempts:
            return None
        latest_attempt = attempts[0]
        profile = get(session, Profile, self.tenant_record_id)
        current_key = ai.cache_key(
            comparison, profile, self.settings, self.prompt_settings, output_locale
        )
        analysis = next(
            (item for item in attempts if item.status == "succeeded" and item.cache_key == current_key),
            next((item for item in attempts if item.status == "succeeded"), latest_attempt),
        )
        response = {
            **as_dict(analysis),
            "stale": analysis.cache_key != current_key,
            "action_decisions": self.action_decisions_for_analysis(session, analysis.id),
        }
        if latest_attempt.id != analysis.id:
            response["latest_attempt"] = {
                "id": latest_attempt.id,
                "status": latest_attempt.status,
                "error": latest_attempt.error,
                "created_at": latest_attempt.created_at.isoformat(),
            }
        return response

    @staticmethod
    def action_decisions_for_analysis(session: Session, analysis_id: str) -> dict:
        records = list(
            session.scalars(
                select(ActionDecision)
                .where(ActionDecision.analysis_id == analysis_id)
                .order_by(ActionDecision.created_at.desc())
            )
        )
        history = [as_dict(record) for record in records]
        current: dict[str, dict] = {}
        for item in history:
            current.setdefault(item["action_key"], item)
        return {"current": current, "history": history}

    def decide_action(
        self,
        comparison_id: str,
        analysis_id: str,
        action_key: str,
        decision: str,
        *,
        assigned_to: str | None,
        scheduled_for: datetime | None,
        rationale: str | None,
        actor_user_id: str | None,
        actor_label: str,
    ) -> dict:
        if decision == "assigned" and not assigned_to:
            raise DomainError("Choose who should own this review action.", 422, "assignee_required")
        if decision == "scheduled" and scheduled_for is None:
            raise DomainError("Choose when this review action is due.", 422, "schedule_required")
        if decision in {"dismissed", "not_applicable"} and not rationale:
            raise DomainError(
                "Record a short reason so the organization can understand this decision.",
                422,
                "rationale_required",
            )
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            analysis = get(session, Analysis, analysis_id)
            if analysis.comparison_id != comparison.id or analysis.status != "succeeded":
                raise DomainError(
                    "The selected report is not a completed report for this comparison.",
                    409,
                    "analysis_not_current",
                )
            actions = (analysis.result or {}).get("actions") or []
            if not any(item.get("action_key") == action_key for item in actions):
                raise DomainError(
                    "The selected review action is not part of this saved report.",
                    404,
                    "action_not_found",
                )
            record = ActionDecision(
                comparison_id=comparison.id,
                analysis_id=analysis.id,
                action_key=action_key,
                decision=decision,
                assigned_to=assigned_to or None,
                scheduled_for=scheduled_for,
                rationale=rationale or None,
                actor_user_id=actor_user_id,
                actor_label=actor_label[:200] or "Workspace administrator",
            )
            session.add(record)
            session.commit()
            return self.action_decisions_for_analysis(session, analysis.id)

    def comparison_detail(
        self, comparison_id: str, output_locale: str = ai.DEFAULT_OUTPUT_LOCALE
    ):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            law = get(session, Law, comparison.law_id)
            identity = self.refresh_comparison_identity(session, comparison)
            profile = get(session, Profile, self.tenant_record_id)
            current_key = ai.cache_key(
                comparison, profile, self.settings, self.prompt_settings, output_locale
            )
            analysis_job = session.scalar(
                select(Job)
                .where(
                    Job.type == "impact_analysis",
                    Job.target_id == comparison.id,
                    Job.idempotency_key == f"impact:{current_key}",
                )
                .order_by(Job.created_at.desc())
                .limit(1)
            )
            session.commit()
            return {
                **as_dict(comparison),
                "old_version": version_summary(old),
                "new_version": version_summary(new),
                "law": as_dict(law),
                "identity": identity,
                "analysis": self.latest_analysis(session, comparison, output_locale),
                "analysis_job": (
                    durable_jobs.serialize(session, analysis_job) if analysis_job else None
                ),
            }

    def create_comparison(self, old_id: str, new_id: str):
        with self.write_guard, self.db.session() as session:
            old, new = get(session, Version, old_id), get(session, Version, new_id)
            comparison = self.ensure_comparison(session, old, new, "saved_versions")
            session.commit()
            comparison_id = comparison.id
        return self.comparison_detail(comparison_id)

    def start_scan(self, law_ids: list[str] | None, baseline_id: str | None):
        with self.write_guard, self.db.session() as session:
            if law_ids is None:
                watches = list(
                    session.scalars(select(DocumentWatch).where(DocumentWatch.active.is_(True)))
                )
                laws = [get(session, Law, watch.law_id) for watch in watches]
            else:
                laws = [get(session, Law, law_id) for law_id in dict.fromkeys(law_ids)]
                watches = []
                for law in laws:
                    watch = self.watch(session, law.id, required=False)
                    if watch is None:
                        watch = DocumentWatch(law_id=law.id, display_name=law.name, active=True)
                        session.add(watch)
                    watches.append(watch)
                session.flush()
            if not laws:
                raise DomainError("Add or select an active law before scanning.")
            if len(laws) > 25:
                raise DomainError("The MVP supports at most 25 documents per scan. Select a smaller batch.")
            if baseline_id and len(laws) != 1:
                raise DomainError("Choose a historical baseline for one law at a time.")
            if any(not watch.active for watch in watches):
                raise DomainError("Resume paused laws before scanning them.")
            if baseline_id and get(session, Version, baseline_id).law_id != laws[0].id:
                raise DomainError("The baseline must belong to the selected law.")
            busy = session.scalar(
                select(ScanItem.id)
                .join(Scan)
                .where(
                    ScanItem.law_id.in_([law.id for law in laws]),
                    Scan.status.in_(["queued", "running"]),
                )
                .limit(1)
            )
            if busy:
                raise DomainError("A selected law already has a scan in progress.", 409, "scan_in_progress")
            scan = Scan(total=len(laws))
            session.add(scan)
            session.flush()
            for law, watch in zip(laws, watches, strict=True):
                selected_baseline = baseline_id or watch.selected_baseline_version_id or law.current_version_id
                if baseline_id:
                    watch.selected_baseline_version_id = baseline_id
                session.add(
                    ScanItem(
                        scan_id=scan.id,
                        law_id=law.id,
                        baseline_version_id=selected_baseline,
                        mode="historical" if baseline_id else "monitoring",
                        events=[{"stage": "queued", "at": utcnow().isoformat()}],
                    )
                )
            durable_jobs.enqueue(
                session,
                job_type="scan",
                target_type="scan",
                target_id=scan.id,
                queue="ingest",
                idempotency_key=f"scan:{scan.id}",
                payload={"scan_id": scan.id},
                progress_total=len(laws),
                max_attempts=self.settings.job_max_attempts,
                steps=[("Scan " + law.name, {"law_id": law.id}) for law in laws],
            )
            session.commit()
            return scan.id

    def stage(self, item_id: str, stage: str, **updates):
        with self.write_guard, self.db.session() as session:
            item = get(session, ScanItem, item_id)
            item.stage = stage
            item.events = [*item.events, {"stage": stage, "at": utcnow().isoformat()}]
            for key, value in updates.items():
                setattr(item, key, value)
            session.commit()

    async def run_scan(self, scan_id: str, job_id: str | None = None, worker: str = "inline"):
        with self.db.session() as session:
            scan = get(session, Scan, scan_id)
            scan.status = "running"
            ids = list(session.scalars(select(ScanItem.id).where(ScanItem.scan_id == scan_id)))
            session.commit()
        completed = 0
        for position, item_id in enumerate(ids, 1):
            if job_id:
                with self.write_guard, self.db.session() as session:
                    if durable_jobs.cancellation_requested(session, job_id):
                        scan = get(session, Scan, scan_id)
                        scan.status, scan.finished_at = "cancelled", utcnow()
                        for pending_id in ids[position - 1 :]:
                            pending = get(session, ScanItem, pending_id)
                            if pending.stage not in {"complete", "failed"}:
                                pending.stage, pending.result = "interrupted", "cancelled"
                        session.commit()
                        raise durable_jobs.JobCancelled()
                    durable_jobs.heartbeat(session, job_id, worker)
                    session.commit()
            with self.db.session() as session:
                existing = get(session, ScanItem, item_id)
                already_done = existing.stage == "complete"
            if already_done:
                completed += 1
                if job_id:
                    with self.write_guard, self.db.session() as session:
                        durable_jobs.progress(
                            session,
                            job_id,
                            current=completed,
                            total=len(ids),
                            step_position=position,
                            step_state="succeeded",
                            step_details={"scan_item_id": item_id, "resumed": True},
                        )
                        session.commit()
                continue
            try:
                await self.run_scan_item(item_id)
                step_state, step_error = "succeeded", None
            except Exception as exc:
                message = (
                    exc.message
                    if isinstance(exc, DomainError)
                    else "An unexpected processing error occurred. The last good version has been preserved."
                )
                if not isinstance(exc, DomainError):
                    logger.exception("Scan item failed: %s", item_id)
                self.stage(item_id, "failed", result="failed", error=message, analysis_status="not_run")
                with self.write_guard, self.db.session() as session:
                    item = get(session, ScanItem, item_id)
                    watch = self.watch(session, item.law_id)
                    watch.last_result, watch.last_error, watch.last_checked = "failed", message, utcnow()
                    session.commit()
                step_state, step_error = "failed", message
            completed += 1
            if job_id:
                with self.write_guard, self.db.session() as session:
                    durable_jobs.progress(
                        session,
                        job_id,
                        current=completed,
                        total=len(ids),
                        step_position=position,
                        step_state=step_state,
                        step_details={"scan_item_id": item_id},
                        step_error=step_error,
                    )
                    session.commit()
        with self.write_guard, self.db.session() as session:
            scan = get(session, Scan, scan_id)
            items = list(session.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id)))
            scan.status = (
                "partial"
                if any(i.result == "failed" or i.analysis_status == "failed" for i in items)
                else "complete"
            )
            scan.finished_at = utcnow()
            session.commit()

    async def run_scan_item(self, item_id: str):
        with self.db.session() as session:
            item = get(session, ScanItem, item_id)
            law = get(session, Law, item.law_id)
            url, provider, live_baseline_id = law.url, law.provider, law.current_version_id
            prior = session.get(Version, live_baseline_id) if live_baseline_id else None
            synthetic = prior.synthetic if prior else False
        enrich_correlation(document_id=law.id)
        self.stage(item_id, "fetching")
        fetched = await self.fetcher.fetch(url, provider)
        self.stage(item_id, "extracting")
        name = PurePosixPath(urlsplit(fetched.url).path).name or "document.html"
        document = await asyncio.to_thread(extract, fetched.body, fetched.content_type, name, provider)
        self.stage(item_id, "comparing")
        with self.write_guard, self.db.session() as session:
            item = get(session, ScanItem, item_id)
            law = get(session, Law, item.law_id)
            version, _ = self.save_snapshot(
                session, law, document, "live", fetched.url, synthetic=synthetic, metadata=fetched.metadata
            )
            item.new_version_id = version.id
            identity = self.refresh_version_identity(session, law, version)
            identity_block = identity["status"] in {"mismatch", "unknown"} and not self.identity_confirmed(
                session, version, identity
            )
            if identity_block:
                item.live_result = f"identity_{identity['status']}"
                self.watch(session, law.id).last_checked = utcnow()
                session.commit()
                raise DomainError(
                    "The newly fetched artifact was saved for inspection but was not made current because its legal-work identity could not be accepted. Inspect the original, attach it to the correct document, or confirm an unknown assignment.",
                    409,
                    f"document_identity_{identity['status']}",
                )
            live_comparison = (
                self.ensure_comparison(
                    session, get(session, Version, live_baseline_id), version, "monitoring"
                )
                if live_baseline_id
                else None
            )
            item.monitoring_comparison_id = live_comparison.id if live_comparison else None
            item.live_result = (
                "baseline_created"
                if not live_comparison
                else "changed"
                if live_comparison.diff["changed"]
                else "unchanged"
            )
            if item.mode == "historical":
                comparison = self.ensure_comparison(
                    session, get(session, Version, item.baseline_version_id), version, "historical"
                )
                item.result = "historical_comparison"
            else:
                comparison, item.result = live_comparison, item.live_result
            item.comparison_id = comparison.id if comparison else None
            law.current_version_id = version.id
            watch = self.watch(session, law.id)
            watch.last_checked = utcnow()
            watch.last_result, watch.last_error = item.live_result, None
            comparison_id = item.comparison_id
            changed = comparison.diff["changed"] if comparison else False
            session.commit()
        status, error = "not_needed", None
        if changed and comparison_id:
            if self.settings.model_configured:
                self.stage(item_id, "analysing")
                result = await self.analyse(comparison_id)
                status, error = result["status"], result.get("error")
            else:
                status = "not_configured"
        self.stage(item_id, "complete", analysis_status=status, error=error)

    def scan_detail(self, scan_id: str):
        with self.db.session() as session:
            scan = get(session, Scan, scan_id)
            items = [
                {**as_dict(item), "law_name": get(session, Law, item.law_id).name}
                for item in session.scalars(
                    select(ScanItem).where(ScanItem.scan_id == scan_id).order_by(ScanItem.created_at)
                )
            ]
            job = session.scalar(
                select(Job).where(Job.target_type == "scan", Job.target_id == scan_id).limit(1)
            )
            return {
                **as_dict(scan),
                "completed": sum(i["stage"] in {"complete", "failed", "interrupted"} for i in items),
                "items": items,
                "job": durable_jobs.serialize(session, job) if job else None,
            }

    def job_detail(self, job_id: str):
        with self.db.session() as session:
            return durable_jobs.serialize(session, get(session, Job, job_id))

    def jobs(self, limit: int = 50, *, workload: str = "all"):
        with self.db.session() as session:
            statement = select(Job)
            if workload == "ai":
                statement = statement.where(
                    Job.type.in_(("ask", "impact_analysis", "relation_impact_analysis"))
                )
            records = list(
                session.scalars(
                    statement.order_by(Job.created_at.desc()).limit(max(1, min(200, limit)))
                )
            )
            return [durable_jobs.serialize(session, record) for record in records]

    def ask_jobs(self, comparison_id: str, limit: int = 20):
        with self.db.session() as session:
            get(session, Comparison, comparison_id)
            records = list(
                session.scalars(
                    select(Job)
                    .where(
                        Job.type == "ask",
                        Job.target_type == "comparison",
                        Job.target_id == comparison_id,
                    )
                    .order_by(Job.created_at.desc())
                    .limit(max(1, min(50, limit)))
                )
            )
            return [durable_jobs.serialize(session, record) for record in records]

    @staticmethod
    def _age_seconds(value: datetime | None, now: datetime) -> int | None:
        if value is None:
            return None
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        return max(0, int((now - aware).total_seconds()))

    async def platform_status(self):
        now = utcnow()
        active_states = ("queued", "dispatched", "running", "retrying", "waiting_for_model")
        database_started = time.perf_counter()
        with self.db.session(include_all_organizations=True) as session:
            job_counts = {
                state: count
                for state, count in session.execute(
                    select(Job.state, func.count()).group_by(Job.state)
                )
            }
            queue_counts = {
                queue: count
                for queue, count in session.execute(
                    select(Job.queue, func.count())
                    .where(Job.state.in_(active_states))
                    .group_by(Job.queue)
                )
            }
            oldest = session.scalar(
                select(Job.created_at)
                .where(Job.state.in_(active_states))
                .order_by(Job.created_at)
                .limit(1)
            )
            failures = [
                {
                    "id": record.id,
                    "type": record.type,
                    "queue": record.queue,
                    "error": record.error_detail,
                    "finished_at": record.finished_at.isoformat() if record.finished_at else None,
                }
                for record in session.scalars(
                    select(Job).where(Job.state == "failed").order_by(Job.updated_at.desc()).limit(8)
                )
            ]
            connectors = [
                {
                    "connector": item.connector,
                    "stream": item.stream,
                    "health": item.health,
                    "message": item.health_message,
                    "last_success_at": item.last_success_at.isoformat()
                    if item.last_success_at
                    else None,
                    "freshness_seconds": self._age_seconds(item.last_success_at, now),
                }
                for item in session.scalars(
                    select(ConnectorState).order_by(ConnectorState.connector, ConnectorState.stream)
                )
            ]
            recent_audit = [
                {
                    "id": item.id,
                    "scope": item.scope,
                    "action": item.action,
                    "result": item.result,
                    "response_status": item.response_status,
                    "actor_kind": item.actor_kind,
                    "created_at": item.created_at.isoformat(),
                }
                for item in session.scalars(
                    select(AdministrativeAudit).order_by(AdministrativeAudit.created_at.desc()).limit(12)
                )
            ]
            resources = {
                "organizations": session.scalar(select(func.count()).select_from(Organization)) or 0,
                "users": session.scalar(select(func.count()).select_from(User)) or 0,
                "memberships": session.scalar(select(func.count()).select_from(OrganizationMembership)) or 0,
                "active_watches": session.scalar(
                    select(func.count()).select_from(DocumentWatch).where(DocumentWatch.active.is_(True))
                )
                or 0,
                "custom_sources": session.scalar(select(func.count()).select_from(Source)) or 0,
            }
            ai_triage = summarize_ai_triage_metrics(
                session.scalars(select(Analysis).order_by(Analysis.created_at.desc()).limit(1000)),
                session.scalars(select(AskRecord).order_by(AskRecord.created_at.desc()).limit(1000)),
                session.scalars(
                    select(Comparison).order_by(Comparison.created_at.desc()).limit(1000)
                ),
                session.scalars(
                    select(ActionDecision).order_by(ActionDecision.created_at.desc()).limit(2000)
                ),
                session.scalars(
                    select(OrganizationRelationReview)
                    .order_by(OrganizationRelationReview.created_at.desc())
                    .limit(2000)
                ),
            )
        database_latency_ms = round((time.perf_counter() - database_started) * 1000)

        disk = shutil.disk_usage(self.environment_settings.storage_path)
        backup_path = self.environment_settings.storage_path / "backups"
        backup_files = sorted(
            (path for path in backup_path.glob("*") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ) if backup_path.exists() else []
        newest_backup = (
            datetime.fromtimestamp(backup_files[0].stat().st_mtime, tz=UTC) if backup_files else None
        )
        cleanup_marker = self.environment_settings.storage_path / "operations" / "last-cleanup.json"
        try:
            last_cleanup = json.loads(cleanup_marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last_cleanup = None
        def ping_redis():
            client = Redis.from_url(
                    self.environment_settings.redis_url,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            try:
                return client.ping()
            finally:
                client.close()

        redis_started = time.perf_counter()
        try:
            redis_ok = await asyncio.to_thread(ping_redis)
        except RedisError:
            redis_ok = False
        redis_latency_ms = round((time.perf_counter() - redis_started) * 1000)
        try:
            inventory = await self.model_manager.inventory()
            deployment = inventory.get("deployment") or {}
            hardware = inventory.get("hardware") or {}
            model = {
                "available": True,
                "state": deployment.get("state", "stopped"),
                "model_id": deployment.get("model_id"),
                "available_slots": deployment.get("available_slots", 0),
                "accepted_slots": deployment.get("accepted_slots", 0),
                "cuda_devices": hardware.get("cuda_devices", []),
                "ram_bytes": hardware.get("ram_bytes"),
                "disk_free_bytes": hardware.get("disk_free_bytes"),
                "probed_at": hardware.get("probed_at"),
                "benchmark": deployment.get("benchmark")
                or {
                    "status": "required",
                    "message": "Run the target-host stability benchmark before public use.",
                },
                "admission": inventory.get("admission")
                or {
                    "slots": 0,
                    "busy_slots": 0,
                    "available_slots": 0,
                    "waiting": 0,
                },
            }
        except DomainError as exc:
            model = {"available": False, "state": "unavailable", "error": exc.message}
        return {
            "scope": "platform",
            "generated_at": now.isoformat(),
            "services": {
                "api": "healthy",
                "database": "healthy",
                "redis": "healthy" if redis_ok else "unavailable",
                "model_manager": "healthy" if model["available"] else "unavailable",
            },
            "api_metrics": self.api_metrics.snapshot(),
            "dependency_metrics": {
                "database": {
                    "healthy": True,
                    "query_ms": database_latency_ms,
                    "pool_size_per_process": self.environment_settings.database_pool_size,
                    "max_overflow_per_process": self.environment_settings.database_max_overflow,
                    "pool_timeout_seconds": self.environment_settings.database_pool_timeout_seconds,
                },
                "redis": {"healthy": bool(redis_ok), "ping_ms": redis_latency_ms},
            },
            "resources": resources,
            "ai_triage": ai_triage,
            "jobs": {
                "states": job_counts,
                "queues": queue_counts,
                "oldest_active_age_seconds": self._age_seconds(oldest, now),
                "dead_letters": job_counts.get("failed", 0),
                "recent_failures": failures,
            },
            "connectors": connectors,
            "model": model,
            "storage": {
                "total_bytes": disk.total,
                "free_bytes": disk.free,
                "used_bytes": disk.used,
                "retention": {
                    "document_evidence": "immutable",
                    "ai_history": "user_retained",
                    "integration_logs_days": self.environment_settings.integration_log_retention_days,
                    "terminal_jobs_days": self.environment_settings.job_history_retention_days,
                    "orphan_artifacts_hours": self.environment_settings.orphan_artifact_retention_hours,
                    "last_cleanup_at": (last_cleanup or {}).get("completed_at"),
                    "candidate_ttl_days": self.environment_settings.relation_candidate_ttl_days,
                },
            },
            "backup": {
                "configured": backup_path.exists(),
                "latest_at": newest_backup.isoformat() if newest_backup else None,
                "age_seconds": self._age_seconds(newest_backup, now),
                "file_count": len(backup_files),
                "status": "available" if newest_backup else "not_configured",
            },
            "recent_audit": recent_audit,
        }

    def deployment_status(self):
        return deployment_snapshot(self.environment_settings.deployment_status_path)

    def organization_status(self):
        now = utcnow()
        with self.db.session() as session:
            quota = session.scalar(select(OrganizationQuota))
            profile = session.scalar(select(Profile))
            prompt = session.scalar(select(PromptConfiguration))
            platform_prompt = session.get(PlatformPromptConfiguration, "default")
            model_record = session.scalar(select(ApertusConfiguration))
            analyses = list(session.scalars(select(Analysis).order_by(Analysis.created_at.desc()).limit(500)))
            questions = list(session.scalars(select(AskRecord).order_by(AskRecord.created_at.desc()).limit(500)))
            token_counts: dict[str, int] = {}
            for record in [*analyses, *questions]:
                for key, value in (record.provenance or {}).get("token_counts", {}).items():
                    if isinstance(value, int):
                        token_counts[key] = token_counts.get(key, 0) + value
            recent_audit = [
                {
                    "action": item.action,
                    "result": item.result,
                    "response_status": item.response_status,
                    "created_at": item.created_at.isoformat(),
                }
                for item in session.scalars(
                    select(AdministrativeAudit)
                    .where(AdministrativeAudit.organization_id == self.organization_id)
                    .order_by(AdministrativeAudit.created_at.desc())
                    .limit(8)
                )
            ]
            settings = public_settings(self.settings, model_record)
            return {
                "scope": "organization",
                "generated_at": now.isoformat(),
                "workspace": {
                    "members": session.scalar(
                        select(func.count()).select_from(OrganizationMembership)
                    )
                    or 0,
                    "pending_invitations": session.scalar(
                        select(func.count())
                        .select_from(OrganizationInvitation)
                        .where(
                            OrganizationInvitation.accepted_at.is_(None),
                            OrganizationInvitation.revoked_at.is_(None),
                            OrganizationInvitation.expires_at > now,
                        )
                    )
                    or 0,
                    "active_watches": session.scalar(
                        select(func.count())
                        .select_from(DocumentWatch)
                        .where(DocumentWatch.active.is_(True))
                    )
                    or 0,
                    "custom_sources": session.scalar(select(func.count()).select_from(Source)) or 0,
                },
                "profile": {
                    "name": profile.name if profile else "",
                    "revision": profile.revision if profile else 0,
                    "complete": bool(profile and profile.description.strip()),
                },
                "prompts": {
                    "source": "organization_override" if prompt else "platform_default",
                    "revision": prompt.revision if prompt else platform_prompt.revision if platform_prompt else 1,
                },
                "ai": {
                    "provider": settings["provider"],
                    "execution": "local" if settings["provider"] == "docker" else "cloud",
                    "cloud_opt_in": settings["provider"] != "docker",
                    "credential_configured": settings["api_key_configured"],
                    "analyses": len(analyses),
                    "questions": len(questions),
                    "token_counts": token_counts,
                },
                "quotas": quota.values if quota else {},
                "recent_audit": recent_audit,
            }

    def cancel_job(self, job_id: str):
        with self.write_guard, self.db.session() as session:
            try:
                job = durable_jobs.request_cancel(session, job_id)
            except LookupError as exc:
                raise DomainError("The requested job was not found.", 404, "not_found") from exc
            if job.state == "cancelled" and job.type == "scan":
                scan = session.get(Scan, job.target_id)
                if scan and scan.status in {"queued", "running"}:
                    scan.status, scan.finished_at = "cancelled", utcnow()
                    for item in session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)):
                        if item.stage not in {"complete", "failed"}:
                            item.stage, item.result = "interrupted", "cancelled"
            session.commit()
            return durable_jobs.serialize(session, job)

    async def model_inventory(self, refresh_hardware: bool = False):
        if refresh_hardware:
            await self.model_manager.probe()
        return await self.model_manager.inventory()

    async def assistant_runtime(self):
        """Expose the local-only workload selection used by the product assistant."""
        return await self.model_manager.profile("assistant-lite")

    async def assistant_remark(self, data: AssistantRemarkInput):
        """Generate one bounded quip using only server-validated product context."""
        messages = assistant_remark_messages(data)
        completion = None
        last_error = None
        for attempt in range(2):
            completion = await self.model_manager.complete_profile(
                "assistant-lite",
                self.organization_id,
                messages,
                max_tokens=24,
                response_schema=assistant_remark_schema(data),
            )
            try:
                payload = json.loads(completion["content"])
                if set(payload) != {"angle"} or payload["angle"] not in {
                    "bureaucracy",
                    "evidence",
                    "queue",
                    "progress",
                }:
                    raise ValueError("remark JSON does not match the exact schema")
                remark_key = f"companion.generated.{payload['angle']}"
                break
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 0:
                    messages = [
                        *messages,
                        {"role": "assistant", "content": completion["content"][:500]},
                        {
                            "role": "user",
                            "content": (
                                "Repair the answer. Return exactly one JSON object with only an angle "
                                "field using one of the allowed values."
                            ),
                        },
                    ]
        else:
            raise DomainError(
                "The local assistant returned an unusable remark.",
                502,
                "assistant_response_invalid",
            ) from last_error
        profile = completion["profile"]
        model = profile["selected_model"]
        return {
            "key": remark_key,
            "locale": data.locale,
            "trigger": data.trigger,
            "provenance": {
                "profile": profile["id"],
                "persona_version": ASSISTANT_PERSONA_VERSION,
                "model": model["served_model_id"],
                "model_revision": model.get("immutable_revision"),
                "local": True,
                "cloud_fallback": False,
            },
        }

    async def assistant_chat(
        self,
        data: AssistantChatInput,
        *,
        locale: str,
        route: str,
        entity_kind: str | None,
        entity_label: str,
        history: list[dict],
    ):
        """Answer a personal companion turn without creating an uncited legal path."""
        route_reply = assistant_route_help(data.message, locale, route, data.tone)
        if route_reply:
            return {
                "reply": route_reply,
                "requires_cited_ask": False,
                "provenance": {
                    "profile": "assistant-router",
                    "persona_version": ASSISTANT_PERSONA_VERSION,
                    "model": "deterministic-route-help",
                    "model_revision": None,
                    "local": True,
                    "cloud_fallback": False,
                },
            }
        messages = assistant_chat_messages(
            message=data.message,
            locale=locale,
            tone=data.tone,
            route=route,
            entity_kind=entity_kind,
            entity_label=entity_label,
            history=history,
        )
        completion = None
        last_error = None
        for attempt in range(2):
            completion = await self.model_manager.complete_profile(
                "assistant-lite",
                self.organization_id,
                messages,
                max_tokens=260,
                response_schema=ASSISTANT_CHAT_SCHEMA,
            )
            try:
                payload = json.loads(completion["content"])
                if set(payload) != {"reply", "requires_cited_ask"}:
                    raise ValueError("chat JSON does not match the exact schema")
                if not isinstance(payload["reply"], str) or not payload["reply"].strip():
                    raise ValueError("chat reply is empty")
                if len(payload["reply"]) > 900 or not isinstance(
                    payload["requires_cited_ask"], bool
                ):
                    raise ValueError("chat fields are invalid")
                lowered_reply = payload["reply"].lower()
                leaked_markers = (
                    "requires_cited_ask",
                    "return json",
                    "screen_purpose",
                    "supplied schema",
                    "these instructions",
                    "persona marvin-local",
                )
                if any(marker in lowered_reply for marker in leaked_markers):
                    raise ValueError("chat reply exposed an internal instruction")
                payload["reply"] = payload["reply"].strip()
                break
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 0:
                    messages = [
                        *messages,
                        {"role": "assistant", "content": str(completion.get("content", ""))[:900]},
                        {
                            "role": "user",
                            "content": (
                                "Repair the answer. Return exactly one JSON object with only reply "
                                "and requires_cited_ask fields matching the schema."
                            ),
                        },
                    ]
        else:
            raise DomainError(
                "The local assistant returned an unusable chat response.",
                502,
                "assistant_response_invalid",
            ) from last_error
        profile = completion["profile"]
        model = profile["selected_model"]
        return {
            **payload,
            "provenance": {
                "profile": profile["id"],
                "persona_version": ASSISTANT_PERSONA_VERSION,
                "model": model["served_model_id"],
                "model_revision": model.get("immutable_revision"),
                "local": True,
                "cloud_fallback": False,
            },
        }

    async def accept_model_license(self, model_id: str, accepted: bool):
        return await self.model_manager.accept_license(model_id, accepted)

    async def model_command(self, model_id: str, action: str):
        if action in {"download", "start"}:
            inventory = await self.model_manager.inventory()
            model = next((item for item in inventory["models"] if item["id"] == model_id), None)
            if not model:
                raise DomainError("This model is not in the versioned allowlist.", 404, "model_not_allowed")
            if action == "start":
                current = self.apertus_configuration()
                self.save_model_settings(
                    ApertusSettingsInput(
                        provider="docker",
                        model=model["served_model_id"],
                        timeout_seconds=current["timeout_seconds"],
                        request_retries=current["request_retries"],
                        batch_concurrency=1,
                        context_chars=min(
                            current["context_chars"],
                            model["requirements"]["recommended_context"] * 4,
                        ),
                        max_tokens=min(current["max_tokens"], 700),
                        temperature=current["temperature"],
                        top_p=current["top_p"],
                        presence_penalty=current["presence_penalty"],
                        reasoning_effort="none",
                        json_mode=current["json_mode"],
                        key_action="keep",
                    )
                )
            with self.write_guard, self.db.session() as session:
                existing = session.scalar(
                    select(Job)
                    .where(
                        Job.type == f"model_{action}",
                        Job.target_id == model_id,
                        Job.state.in_(["queued", "dispatched", "running", "retrying"]),
                    )
                    .order_by(Job.created_at.desc())
                    .limit(1)
                )
                if existing:
                    existing_result = durable_jobs.serialize(session, existing)
                else:
                    existing_result = None
                if existing_result is None:
                    steps = (
                        [
                            ("Transfer resumable artifact", {"model_id": model_id}),
                            ("Verify SHA-256", {"sha256": model["sha256"]}),
                            ("Activate model artifact", {}),
                        ]
                        if action == "download"
                        else [
                            ("Validate hardware profile", {"model_id": model_id}),
                            ("Start pinned llama.cpp runtime", {}),
                            ("Wait for inference health", {}),
                        ]
                    )
                    job, _ = durable_jobs.enqueue(
                        session,
                        job_type=f"model_{action}",
                        target_type="local_model",
                        target_id=model_id,
                        queue="maintenance",
                        priority=7,
                        idempotency_key=f"model:{action}:{model_id}:{time.time_ns()}",
                        payload={"cached": bool(model["download"].get("cached_copy_available"))},
                        progress_total=model["size_bytes"] if action == "download" else 3,
                        max_attempts=self.settings.job_max_attempts,
                        steps=steps,
                    )
                    session.commit()
                    existing_result = durable_jobs.serialize(session, job)
            if action == "download" and model["state"] == "paused":
                await self.model_manager.command(
                    model_id,
                    "download",
                    cached=bool(model["download"].get("cached_copy_available")),
                )
            return existing_result
        if action == "remove":
            inventory = await self.model_manager.inventory()
            model = next((item for item in inventory["models"] if item["id"] == model_id), None)
            if not model:
                raise DomainError("This model is not in the versioned allowlist.", 404, "model_not_allowed")
            served_ids = {model_id, model["served_model_id"]}
            with self.db.session() as session:
                referenced = bool(
                    session.scalar(select(Analysis.id).where(Analysis.model.in_(served_ids)).limit(1))
                    or session.scalar(select(AskRecord.id).where(AskRecord.model.in_(served_ids)).limit(1))
                )
            return await self.model_manager.command(model_id, action, referenced=referenced)
        result = await self.model_manager.command(model_id, action)
        if action == "cancel":
            with self.write_guard, self.db.session() as session:
                job = session.scalar(
                    select(Job)
                    .where(
                        Job.type == "model_download",
                        Job.target_id == model_id,
                        Job.state.in_(["queued", "dispatched", "running", "retrying"]),
                    )
                    .order_by(Job.created_at.desc())
                    .limit(1)
                )
                if job:
                    durable_jobs.request_cancel(session, job.id)
                    session.commit()
        return result

    @staticmethod
    def _inventory_model(inventory: dict, model_id: str) -> dict:
        model = next((item for item in inventory.get("models", []) if item.get("id") == model_id), None)
        if not model:
            raise DomainError("The model disappeared from the local allowlist.", 404, "model_not_allowed")
        return model

    async def _run_model_job(self, job_id: str, model_id: str, action: str, payload: dict, worker: str):
        await self.model_manager.command(model_id, action, cached=payload.get("cached", False))
        while True:
            await asyncio.sleep(1)
            with self.write_guard, self.db.session() as session:
                if not durable_jobs.heartbeat(session, job_id, worker):
                    session.commit()
                    if action == "download":
                        await self.model_manager.command(model_id, "cancel")
                    raise durable_jobs.JobCancelled()
                session.commit()
            inventory = await self.model_manager.inventory()
            model = self._inventory_model(inventory, model_id)
            state = model["state"]
            if action == "download":
                downloaded = int(model["download"]["downloaded_bytes"])
                total = int(model["download"]["total_bytes"])
                position = 2 if state == "verifying" else 3 if model["installed"] else 1
                with self.write_guard, self.db.session() as session:
                    durable_jobs.progress(
                        session,
                        job_id,
                        current=downloaded,
                        total=total,
                        step_position=position,
                        step_state="running" if not model["installed"] else "succeeded",
                        step_details={"state": state, "downloaded_bytes": downloaded},
                    )
                    if position > 1:
                        durable_jobs.progress(session, job_id, current=downloaded, step_position=1, step_state="succeeded")
                    if position > 2:
                        durable_jobs.progress(session, job_id, current=downloaded, step_position=2, step_state="succeeded")
                    session.commit()
                if model["installed"]:
                    return {"model": model, "runtime_image": inventory["runtime_image"]}
            else:
                position = 1 if state in {"available", "stopped"} else 2 if state == "starting" else 3
                with self.write_guard, self.db.session() as session:
                    durable_jobs.progress(session, job_id, current=position - 1, total=3, step_position=position, step_state="running")
                    if position > 1:
                        durable_jobs.progress(session, job_id, current=position - 1, step_position=1, step_state="succeeded")
                    if position > 2:
                        durable_jobs.progress(session, job_id, current=position - 1, step_position=2, step_state="succeeded")
                    session.commit()
                if state == "ready":
                    with self.write_guard, self.db.session() as session:
                        durable_jobs.progress(session, job_id, current=3, step_position=3, step_state="succeeded")
                        session.commit()
                    return {"model": model, "deployment": inventory.get("deployment")}
            if state == "paused" and action == "download":
                continue
            if state in {"error", "incompatible", "degraded", "paused"}:
                raise DomainError(
                    model.get("error") or f"The local model entered the {state} state.",
                    422,
                    f"model_{state}",
                )

    def retry_job(self, job_id: str):
        with self.write_guard, self.db.session() as session:
            try:
                job = durable_jobs.retry(session, job_id)
            except LookupError as exc:
                raise DomainError("The requested job was not found.", 404, "not_found") from exc
            if job.type == "scan" and job.state == "queued":
                scan = session.get(Scan, job.target_id)
                if scan:
                    scan.status, scan.finished_at = "queued", None
                    for item in session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)):
                        if item.stage in {"failed", "interrupted"}:
                            item.stage, item.result, item.error = "queued", None, None
            session.commit()
            return durable_jobs.serialize(session, job)

    async def execute_job(self, job_id: str, worker: str = "inline"):
        with self.write_guard, self.db.session() as session:
            job = durable_jobs.claim(session, job_id, worker)
            session.commit()
            if not job:
                return self.job_detail(job_id)
            job_type, target_id, payload = job.type, job.target_id, dict(job.payload or {})

        if (
            job_type in {"impact_analysis", "ask", "relation_impact_analysis"}
            and self.settings.apertus_provider == "docker"
            and isinstance(self.model_client, ai.ModelClient)
        ):
            waiting_reason = None
            try:
                inventory = await self.model_manager.inventory()
                deployment = inventory.get("deployment") or {}
                if deployment.get("state") not in {"ready", "degraded"}:
                    configured = self.settings.apertus_model
                    model = next(
                        (item for item in inventory.get("models", []) if item.get("id") == configured),
                        None,
                    )
                    if model and model.get("installed") and deployment.get("state") not in {"starting"}:
                        await self.model_manager.command(configured, "start")
                        waiting_reason = f"Starting the verified local model {configured}."
                    elif deployment.get("state") == "starting":
                        waiting_reason = f"Warming up the local model {configured}."
                    elif not model or not model.get("installed"):
                        waiting_reason = f"Download and start the local model {configured} from Local models."
                    else:
                        waiting_reason = f"Waiting for local model {configured}."
            except DomainError:
                waiting_reason = "Waiting for the private local model manager to become available."
            if waiting_reason:
                with self.write_guard, self.db.session() as session:
                    durable_jobs.defer_for_model(session, job_id, waiting_reason)
                    session.commit()
                return self.job_detail(job_id)

        def mark(current: int, position: int, state: str):
            with self.write_guard, self.db.session() as session:
                if not durable_jobs.heartbeat(session, job_id, worker):
                    session.commit()
                    raise durable_jobs.JobCancelled()
                durable_jobs.progress(
                    session,
                    job_id,
                    current=current,
                    step_position=position,
                    step_state=state,
                )
                session.commit()

        try:
            if job_type == "scan":
                await self.run_scan(target_id, job_id=job_id, worker=worker)
                result_type, result_id, result_url = "scan", target_id, f"/activity?scan={target_id}"
                result_json = {"scan_id": target_id}
            elif job_type == "impact_analysis":
                mark(1, 1, "succeeded")
                with self.db.session() as session:
                    comparison = get(session, Comparison, target_id)
                    old, new = (
                        get(session, Version, comparison.old_version_id),
                        get(session, Version, comparison.new_version_id),
                    )
                    profile = get(session, Profile, self.tenant_record_id)
                    plan, _ = ai.build_impact_plan(
                        self.settings, comparison, old, new, profile
                    )
                    group_total = max(1, int(plan["execution"]["batch_count"]))

                async def report_group_progress(current: int, total: int):
                    with self.write_guard, self.db.session() as progress_session:
                        if not durable_jobs.heartbeat(progress_session, job_id, worker):
                            progress_session.commit()
                            raise durable_jobs.JobCancelled()
                        durable_jobs.progress(
                            progress_session,
                            job_id,
                            current=1,
                            step_position=2,
                            step_state="running",
                            step_details={"stage": "analysing", "group_total": total},
                            step_current=current,
                            step_total=total,
                        )
                        progress_session.commit()

                with self.write_guard, self.db.session() as progress_session:
                    durable_jobs.progress(
                        progress_session,
                        job_id,
                        current=1,
                        step_position=2,
                        step_state="running",
                        step_details={"stage": "analysing", "group_total": group_total},
                        step_current=0,
                        step_total=group_total,
                    )
                    progress_session.commit()
                result_json = await self.analyse(
                    target_id,
                    progress_callback=report_group_progress,
                    output_locale=payload.get("output_locale", ai.DEFAULT_OUTPUT_LOCALE),
                )
                if result_json.get("status") != "succeeded":
                    raise DomainError(
                        result_json.get("error") or "The impact analysis failed.",
                        502,
                        "analysis_failed",
                    )
                with self.write_guard, self.db.session() as progress_session:
                    durable_jobs.progress(
                        progress_session,
                        job_id,
                        current=2,
                        step_position=2,
                        step_state="succeeded",
                        step_current=group_total,
                        step_total=group_total,
                    )
                    durable_jobs.progress(
                        progress_session,
                        job_id,
                        current=2,
                        step_position=3,
                        step_state="running",
                        step_details={"stage": "validating"},
                    )
                    progress_session.commit()
                mark(3, 3, "succeeded")
                result_type = "analysis"
                result_id = result_json["id"]
                result_url = f"/compare/{target_id}#impact"
            elif job_type == "ask":
                mark(0, 1, "running")

                async def report_ask_progress(stage: str):
                    with self.write_guard, self.db.session() as progress_session:
                        if not durable_jobs.heartbeat(progress_session, job_id, worker):
                            progress_session.commit()
                            raise durable_jobs.JobCancelled()
                        if stage == "evidence_selected":
                            durable_jobs.progress(
                                progress_session,
                                job_id,
                                current=1,
                                step_position=1,
                                step_state="succeeded",
                                step_details={"stage": "selecting_evidence"},
                            )
                            durable_jobs.progress(
                                progress_session,
                                job_id,
                                current=1,
                                step_position=2,
                                step_state="running",
                                step_details={"stage": "generating"},
                            )
                        elif stage == "generated":
                            durable_jobs.progress(
                                progress_session,
                                job_id,
                                current=2,
                                step_position=2,
                                step_state="succeeded",
                                step_details={"stage": "generating"},
                            )
                            durable_jobs.progress(
                                progress_session,
                                job_id,
                                current=2,
                                step_position=3,
                                step_state="running",
                                step_details={"stage": "validating"},
                            )
                        progress_session.commit()

                result_json = await self.ask(
                    target_id,
                    payload.get("question", ""),
                    payload.get("history", []),
                    output_locale=payload.get("output_locale"),
                    progress_callback=report_ask_progress,
                )
                # Cached and deterministic answers can finish before the model stages run.
                mark(1, 1, "succeeded")
                mark(2, 2, "succeeded")
                mark(3, 3, "succeeded")
                result_type = "answer"
                result_id = result_json["record_id"]
                result_url = f"/compare/{target_id}#ask"
            elif job_type == "relation_impact_analysis":
                mark(1, 1, "succeeded")
                mark(1, 2, "running")
                result_json = await self.analyse_relation_candidate(
                    target_id,
                    payload.get("runtime_fingerprint"),
                    force=bool(payload.get("force")),
                    output_locale=payload.get(
                        "output_locale", relation_ai.DEFAULT_OUTPUT_LOCALE
                    ),
                )
                if result_json.get("status") != "succeeded":
                    raise DomainError(
                        result_json.get("error") or "The relation impact analysis failed.",
                        502,
                        "relation_analysis_failed",
                    )
                mark(2, 2, "succeeded")
                mark(2, 3, "running")
                mark(3, 3, "succeeded")
                result_type = "relation_impact_analysis"
                result_id = result_json["id"]
                result_url = f"/impact?candidate={target_id}"
            elif job_type == "digest_delivery":
                mark(0, 1, "running")
                result_json = await asyncio.to_thread(
                    digests.deliver, self.db, self.environment_settings, target_id
                )
                mark(1, 1, "succeeded")
                mark(1, 2, "running")
                mark(2, 2, "succeeded")
                result_type = "digest_delivery"
                result_id = target_id
                result_url = "/digests"
            elif job_type in {"model_download", "model_start"}:
                action = job_type.removeprefix("model_")
                result_json = await self._run_model_job(job_id, target_id, action, payload, worker)
                result_type, result_id, result_url = "local_model", target_id, "/models"
            elif job_type == "connector_sync":
                mark(0, 1, "running")
                result_json = await self._run_connector_job(
                    payload.get("run_id", ""),
                    payload.get("connector", ""),
                    payload.get("stream", ""),
                )
                mark(1, 1, "succeeded")
                mark(2, 2, "succeeded")
                mark(3, 3, "succeeded")
                result_type = "connector_run"
                result_id = payload.get("run_id")
                result_url = "/connectors"
            elif job_type == "source_pack_backfill":
                mark(0, 1, "running")
                with self.write_guard, self.db.session() as session:
                    result_json = source_packs.run_backfill(session, target_id)
                    session.commit()
                mark(1, 1, "succeeded")
                result_type = "source_pack_subscription"
                result_id = target_id
                result_url = "/sources#source-packs"
            elif job_type in {"topic_match_backfill", "topic_match_event"}:
                with self.write_guard, self.db.session() as session:
                    batch_job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
                    if batch_job.state != "running" or batch_job.lease_owner != worker:
                        return self.job_detail(job_id)
                    if batch_job.cancel_requested:
                        raise durable_jobs.JobCancelled()
                    batch_options = {
                        "checkpoint": (batch_job.payload or {}).get("checkpoint"),
                        "captured_at": batch_job.started_at,
                    }
                    if job_type == "topic_match_event":
                        result_json = topic_matching.run_live_batch(
                            session, target_id, self.settings,
                            admission_id=payload.get("admission_id", ""),
                            evidence_fingerprint=payload.get("evidence_fingerprint", ""),
                            **batch_options,
                        )
                        result_type = "regulatory_event"
                    else:
                        result_json = topic_matching.run_backfill(
                            session, target_id, int(payload.get("revision") or 0),
                            self.settings, **batch_options,
                        )
                        result_type = "monitoring_topic"
                    batch_job.payload = {**(batch_job.payload or {}), "checkpoint": result_json["checkpoint"]}
                    batch_job.result_type, batch_job.result_id, batch_job.result_url = result_type, target_id, "/topics"
                    batch_job.result_json = result_json
                    durable_jobs.progress(
                        session, job_id, current=result_json.get("processed", 0),
                        total=result_json.get("processed", 0) + result_json.get("remaining", 0),
                        step_position=1, step_state="pending" if result_json["has_more"] else "succeeded",
                        step_details={"status": result_json["status"], "batches": result_json.get("batches", 0)},
                    )
                    if result_json["has_more"]:
                        durable_jobs.yield_batch(session, batch_job)
                    else:
                        durable_jobs.complete(session, job_id, result_type=result_type,
                                              result_id=target_id, result_url="/topics", result_json=result_json)
                        # Superseded or empty scans must not appear to have examined more events.
                        batch_job.progress_current = result_json.get("processed", 0)
                    session.commit()
                return self.job_detail(job_id)
            else:
                raise DomainError("This durable job type is not supported by the worker.", 422, "job_type_unknown")
        except durable_jobs.JobCancelled:
            with self.write_guard, self.db.session() as session:
                durable_jobs.cancel(session, job_id)
                session.commit()
            return self.job_detail(job_id)
        except Exception as exc:
            detail = exc.message if isinstance(exc, DomainError) else str(exc)
            code = exc.code if isinstance(exc, DomainError) else "job_failed"
            with self.write_guard, self.db.session() as session:
                failed_job = durable_jobs.fail(session, job_id, code=code, detail=detail)
                if job_type == "connector_sync" and payload.get("run_id"):
                    run = synchronization.fail_run(session, payload["run_id"], detail)
                    run.status = failed_job.state
                if job_type == "source_pack_backfill":
                    source_packs.fail_backfill(session, target_id, detail)
                session.commit()
            if not isinstance(exc, DomainError):
                logger.exception("Durable job failed: %s", job_id)
            return self.job_detail(job_id)
        with self.write_guard, self.db.session() as session:
            durable_jobs.complete(
                session,
                job_id,
                result_type=result_type,
                result_id=result_id,
                result_url=result_url,
                result_json=result_json,
            )
            session.commit()
        return self.job_detail(job_id)

    def integration_logs(
        self,
        *,
        query: str = "",
        provider: str = "",
        status: str = "",
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ):
        columns = {
            "created_at": IntegrationLog.created_at,
            "provider": IntegrationLog.provider,
            "operation": IntegrationLog.operation,
            "status": IntegrationLog.status,
            "duration_ms": IntegrationLog.duration_ms,
            "response_status": IntegrationLog.response_status,
        }
        conditions = []
        if query.strip():
            escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    IntegrationLog.provider.ilike(pattern, escape="\\"),
                    IntegrationLog.operation.ilike(pattern, escape="\\"),
                    IntegrationLog.url.ilike(pattern, escape="\\"),
                    IntegrationLog.request_id.ilike(pattern, escape="\\"),
                )
            )
        if provider:
            conditions.append(IntegrationLog.provider == provider)
        if status:
            conditions.append(IntegrationLog.status == status)
        column = columns.get(sort_by, IntegrationLog.created_at)
        ordering = column.asc() if sort_dir == "asc" else column.desc()
        with self.db.session() as session:
            total = session.scalar(
                select(func.count()).select_from(IntegrationLog).where(*conditions)
            )
            records = list(
                session.scalars(
                    select(IntegrationLog)
                    .where(*conditions)
                    .order_by(ordering, IntegrationLog.created_at.desc(), IntegrationLog.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            providers = list(
                session.scalars(
                    select(IntegrationLog.provider).distinct().order_by(IntegrationLog.provider)
                )
            )
        omitted = {"request_headers", "request_body", "response_headers", "response_body"}
        return {
            "items": [as_dict(record, omitted) for record in records],
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "providers": providers,
        }

    def integration_log_detail(self, log_id: str):
        with self.db.session() as session:
            return as_dict(get(session, IntegrationLog, log_id))

    def clear_integration_logs(self):
        with self.write_guard, self.db.session() as session:
            result = session.execute(
                delete(IntegrationLog).where(
                    IntegrationLog.organization_id == self.organization_id
                )
            )
            session.commit()
            return {"deleted": result.rowcount or 0}

    async def relation_runtime_fingerprint(self) -> str:
        runtime: dict = {
            "provider": self.settings.apertus_provider,
            "model": self.settings.apertus_model,
            "endpoint": self.settings.apertus_base_url,
        }
        if self.settings.apertus_provider == "docker":
            try:
                inventory = await self.model_manager.inventory()
                deployment = inventory.get("deployment") or {}
                runtime.update(
                    {
                        "model_revision": deployment.get("model_revision"),
                        "artifact_sha256": deployment.get("artifact_sha256"),
                        "quantization": deployment.get("quantization"),
                        "runtime_image": deployment.get("runtime_image"),
                        "hardware_profile": deployment.get("hardware_profile"),
                    }
                )
            except DomainError as exc:
                runtime["inventory_error"] = exc.code
        return hashlib.sha256(json.dumps(runtime, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _relation_text_tokens(*values: object) -> set[str]:
        value = " ".join(str(item or "") for item in values).casefold()
        return {item for item in re.findall(r"[\wà-ž]{4,}", value) if len(item) >= 4}

    def _relation_analysis_context(
        self,
        session: Session,
        organization_candidate_id: str,
        runtime_fingerprint: str,
        output_locale: str = relation_ai.DEFAULT_OUTPUT_LOCALE,
    ) -> dict:
        delivery = get(session, OrganizationRelationCandidate, organization_candidate_id)
        candidate = get(session, RelationCandidate, delivery.candidate_id)
        event = get(session, RegulatoryEvent, candidate.event_id)
        source_work = get(session, RegulatoryWork, candidate.source_work_id)
        target_work = get(session, RegulatoryWork, candidate.target_work_id)
        relation = session.get(RegulatoryRelation, candidate.relation_id) if candidate.relation_id else None
        source_version = (
            session.get(RegulatoryDocumentVersion, candidate.source_version_id)
            if candidate.source_version_id
            else None
        )
        target_version = (
            session.get(RegulatoryDocumentVersion, candidate.target_version_id)
            if candidate.target_version_id
            else None
        )
        profile = get(session, Profile, self.tenant_record_id)
        official_relation = (
            {
                "id": relation.id,
                "type": relation.relation_type,
                "state": relation.state,
                "authority": relation.authority,
                "provenance_method": relation.provenance_method,
                "evidence_fingerprint": relation.evidence_fingerprint,
                "evidence": relation.evidence_json,
            }
            if relation and relation.state == "confirmed"
            else None
        )
        rows = []
        if official_relation:
            rows.append(
                relation_ai.evidence_row(
                    source_kind="official_relation",
                    label=f"Confirmed official {relation.relation_type} relation",
                    text=json.dumps(relation.evidence_json, ensure_ascii=False, sort_keys=True),
                    source_url=event.source_url or source_work.stable_official_url,
                    work_id=source_work.id,
                    version_id=candidate.source_version_id,
                    authoritative=True,
                    metadata={"relation_id": relation.id, "relation_type": relation.relation_type},
                )
            )
        rows.extend(
            [
                relation_ai.evidence_row(
                    source_kind="regulatory_event",
                    label=f"{event.event_type.replace('_', ' ').title()} event",
                    text=json.dumps(event.evidence_json, ensure_ascii=False, sort_keys=True),
                    source_url=event.source_url,
                    work_id=event.work_id,
                    version_id=event.document_version_id,
                    authoritative=event.provenance_method in {"official_metadata", "exact_identifier"},
                    metadata={
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "provenance_method": event.provenance_method,
                    },
                ),
                relation_ai.evidence_row(
                    source_kind="candidate_fact",
                    label="Deterministic candidate retrieval facts",
                    text=json.dumps(
                        {
                            "why": candidate.why_json,
                            "score_components": candidate.score_components_json,
                            "similarity_is_not_legal_evidence": not bool(official_relation),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    source_url=event.source_url,
                    work_id=target_work.id,
                    authoritative=False,
                    metadata={"candidate_id": candidate.id, "rule_revision": candidate.rule_revision},
                ),
                relation_ai.evidence_row(
                    source_kind="target_lifecycle",
                    label="Current monitored-work lifecycle",
                    text=json.dumps(
                        {
                            "title": target_work.title,
                            "kind": target_work.kind,
                            "authority": target_work.authority,
                            "lifecycle_status": target_work.lifecycle_status or "unknown",
                            "metadata": target_work.metadata_json,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    source_url=target_work.stable_official_url,
                    work_id=target_work.id,
                    version_id=candidate.target_version_id,
                    authoritative=True,
                ),
            ]
        )
        source_passages = list((source_version.passages if source_version else []) or [])
        target_passages = list((target_version.passages if target_version else []) or [])
        target_passage_version_id = target_version.id if target_version else None
        target_passage_source_url = target_version.source_url if target_version else None
        if target_version and target_version.legacy_version_id and not target_passages:
            legacy_target_version = session.get(Version, target_version.legacy_version_id)
            if legacy_target_version:
                target_passages = list(legacy_target_version.passages or [])
                target_passage_version_id = legacy_target_version.id
                target_passage_source_url = legacy_target_version.source_url
        query_tokens = self._relation_text_tokens(
            source_work.title,
            event.evidence_json,
            candidate.why_json,
            source_work.metadata_json,
        )
        target_passages.sort(
            key=lambda passage: (
                -len(query_tokens & self._relation_text_tokens(passage.get("text", ""))),
                int(passage.get("position") or 0),
                str(passage.get("id", "")),
            )
        )
        passages = []
        for index in range(max(len(source_passages), len(target_passages))):
            if index < len(source_passages):
                passages.append(
                    (
                        "event_source_passage",
                        source_version.id,
                        source_version.source_url,
                        source_passages[index],
                    )
                )
            if index < len(target_passages):
                passages.append(
                    (
                        "monitored_work_passage",
                        target_passage_version_id,
                        target_passage_source_url,
                        target_passages[index],
                    )
                )
        for kind, version_id, source_url, passage in passages:
            rows.append(
                relation_ai.evidence_row(
                    source_kind=kind,
                    label=("New event evidence" if kind == "event_source_passage" else "Monitored law evidence"),
                    text=str(passage.get("text", "")),
                    source_url=source_url,
                    work_id=source_work.id if kind == "event_source_passage" else target_work.id,
                    version_id=version_id,
                    passage_id=str(passage.get("id", "")) or None,
                    authoritative=False,
                    metadata={"page": passage.get("page"), "position": passage.get("position")},
                )
            )
        evidence, coverage = relation_ai.select_evidence(rows, self.settings.apertus_context_chars)
        relation_fingerprint = relation.evidence_fingerprint if relation else None
        key = relation_ai.cache_key(
            organization_candidate_id=delivery.id,
            event_id=event.id,
            source_version_id=candidate.source_version_id,
            target_version_id=candidate.target_version_id,
            relation_fingerprint=relation_fingerprint,
            evidence=evidence,
            profile_revision=profile.revision,
            settings=self.settings,
            prompts=self.prompt_settings,
            runtime_fingerprint=runtime_fingerprint,
            output_locale=output_locale,
        )
        plan = relation_ai.build_plan(
            organization_candidate_id=delivery.id,
            event_id=event.id,
            source_version_id=candidate.source_version_id,
            target_version_id=candidate.target_version_id,
            evidence=evidence,
            coverage=coverage,
            profile_revision=profile.revision,
            settings=self.settings,
            output_locale=output_locale,
        )
        plan["runtime_fingerprint"] = runtime_fingerprint
        return {
            "delivery": delivery,
            "candidate": candidate,
            "event": event,
            "source_work": source_work,
            "target_work": target_work,
            "relation": relation,
            "source_version": source_version,
            "target_version": target_version,
            "profile": profile,
            "official_relation": official_relation,
            "evidence": evidence,
            "coverage": coverage,
            "cache_key": key,
            "plan": plan,
        }

    @staticmethod
    def _relation_analysis_dict(record: RelationImpactAnalysis, *, cached: bool = False) -> dict:
        return {
            **as_dict(record, {"evidence_json", "cache_key"}),
            "evidence_count": len(record.evidence_json or []),
            "stale": record.status == "succeeded" and not relation_ai.result_uses_current_rules(record.result),
            "cached": cached,
        }

    async def enqueue_relation_analysis(
        self,
        organization_candidate_id: str,
        runtime_fingerprint: str | None = None,
        *,
        force: bool = False,
        output_locale: str = relation_ai.DEFAULT_OUTPUT_LOCALE,
    ) -> dict:
        runtime_fingerprint = runtime_fingerprint or await self.relation_runtime_fingerprint()
        with self.write_guard, self.db.session() as session:
            context = self._relation_analysis_context(
                session, organization_candidate_id, runtime_fingerprint, output_locale
            )
            if not self.settings.model_configured:
                raise DomainError(
                    "Apertus is not connected. Configure and start the local model before analysing this candidate.",
                    503,
                    "model_not_configured",
                )
            request_key = (
                f"relation-impact:{context['cache_key']}:{secrets.token_hex(8)}"
                if force
                else f"relation-impact:{context['cache_key']}"
            )
            job, reused = durable_jobs.enqueue(
                session,
                job_type="relation_impact_analysis",
                target_type="organization_relation_candidate",
                target_id=organization_candidate_id,
                queue="ai_background",
                idempotency_key=request_key,
                payload={
                    "organization_candidate_id": organization_candidate_id,
                    "event_id": context["event"].id,
                    "runtime_fingerprint": runtime_fingerprint,
                    "force": force,
                    "output_locale": output_locale,
                },
                progress_total=3,
                max_attempts=self.settings.job_max_attempts,
                steps=[
                    ("Prepare relation evidence", {"candidate_id": context["candidate"].id}),
                    ("Analyse possible organizational impact", {"stage": "analysing"}),
                    ("Validate evidence and save conclusion", {"stage": "validating"}),
                ],
            )
            if reused and job.state in {"failed", "cancelled"}:
                job = durable_jobs.retry(session, job.id)
            context["delivery"].status = (
                "analysed" if reused and job.state == "succeeded" else "queued"
            )
            context["delivery"].updated_at = utcnow()
            session.commit()
            return durable_jobs.serialize(session, job)

    async def enqueue_pending_relation_analyses(
        self, deliveries: list[tuple[str, str]]
    ) -> dict:
        """Fan organization deliveries into durable background AI work without blocking ingestion."""

        queued = 0
        waiting_for_configuration = 0
        failed = 0
        runtime_by_organization: dict[str, str] = {}
        for organization_id, delivery_id in deliveries:
            try:
                with self.db.organization_context(organization_id), self.organization_runtime():
                    runtime_fingerprint = runtime_by_organization.get(organization_id)
                    if runtime_fingerprint is None:
                        runtime_fingerprint = await self.relation_runtime_fingerprint()
                        runtime_by_organization[organization_id] = runtime_fingerprint
                    await self.enqueue_relation_analysis(delivery_id, runtime_fingerprint)
                    queued += 1
            except DomainError as exc:
                if exc.code == "model_not_configured":
                    waiting_for_configuration += 1
                else:
                    failed += 1
                    logger.warning(
                        "Could not enqueue relation analysis %s for organization %s: %s",
                        delivery_id,
                        organization_id,
                        exc.code,
                    )
            except Exception:
                failed += 1
                logger.exception(
                    "Could not enqueue relation analysis %s for organization %s",
                    delivery_id,
                    organization_id,
                )
        return {
            "candidates": len(deliveries),
            "queued": queued,
            "waiting_for_configuration": waiting_for_configuration,
            "failed": failed,
        }

    async def analyse_relation_candidate(
        self,
        organization_candidate_id: str,
        runtime_fingerprint: str | None = None,
        *,
        force: bool = False,
        output_locale: str = relation_ai.DEFAULT_OUTPUT_LOCALE,
    ) -> dict:
        runtime_fingerprint = runtime_fingerprint or await self.relation_runtime_fingerprint()
        lock = self.analysis_locks.setdefault(f"relation:{organization_candidate_id}", asyncio.Lock())
        async with lock:
            settings, model_client = self.settings, self.model_client
            prompts = self.prompt_settings.model_copy(deep=True)
            with self.write_guard, self.db.session() as session:
                context = self._relation_analysis_context(
                    session, organization_candidate_id, runtime_fingerprint, output_locale
                )
                cached = (
                    session.scalar(
                        select(RelationImpactAnalysis)
                        .where(
                            RelationImpactAnalysis.cache_key == context["cache_key"],
                            RelationImpactAnalysis.status == "succeeded",
                        )
                        .order_by(RelationImpactAnalysis.created_at.desc())
                        .limit(1)
                    )
                    if not force
                    else None
                )
                if cached:
                    cached.use_count += 1
                    cached.last_used_at = utcnow()
                    context["delivery"].status = "analysed"
                    context["delivery"].updated_at = utcnow()
                    session.commit()
                    return self._relation_analysis_dict(cached, cached=True)
                record = RelationImpactAnalysis(
                    organization_candidate_id=organization_candidate_id,
                    candidate_id=context["candidate"].id,
                    event_id=context["event"].id,
                    target_work_id=context["target_work"].id,
                    cache_key=context["cache_key"],
                    evidence_json=context["evidence"],
                    coverage=context["coverage"],
                    analysis_plan=context["plan"],
                    model=settings.apertus_model,
                    prompt_revision=self.prompt_revision,
                    last_used_at=utcnow(),
                )
                session.add(record)
                session.flush()
                record_id = record.id
                session.commit()
            enrich_correlation(event_id=context["event"].id, analysis_id=record_id)
            trace_token = (
                model_client.begin_trace("background")
                if hasattr(model_client, "begin_trace")
                else None
            )
            try:
                result, coverage = await relation_ai.analyse(
                    model_client,
                    settings,
                    prompts,
                    analysis_id=record_id,
                    evidence=context["evidence"],
                    coverage=context["coverage"],
                    event={
                        "id": context["event"].id,
                        "type": context["event"].event_type,
                        "detected_at": context["event"].detected_at.isoformat(),
                        "authority": context["event"].authority,
                    },
                    source_work={
                        "id": context["source_work"].id,
                        "title": context["source_work"].title,
                        "kind": context["source_work"].kind,
                        "authority": context["source_work"].authority,
                    },
                    target_work={
                        "id": context["target_work"].id,
                        "title": context["target_work"].title,
                        "kind": context["target_work"].kind,
                        "authority": context["target_work"].authority,
                        "lifecycle_status": context["target_work"].lifecycle_status or "unknown",
                    },
                    candidate={
                        "id": context["candidate"].id,
                        "score": context["candidate"].score,
                        "why": context["candidate"].why_json,
                        "similarity_is_not_evidence": not bool(context["official_relation"]),
                    },
                    profile={
                        "name": context["profile"].name,
                        "description": context["profile"].description,
                        "business_areas": context["profile"].business_areas,
                    },
                    official_relation=context["official_relation"],
                    output_locale=output_locale,
                )
                status, error = "succeeded", None
            except Exception as exc:
                result, coverage, status = None, context["coverage"], "failed"
                error = (
                    exc.message
                    if isinstance(exc, DomainError)
                    else "Apertus relation analysis failed. The candidate and saved evidence remain available."
                )
                if not isinstance(exc, DomainError):
                    logger.exception("Relation impact analysis failed")
            trace = (
                model_client.end_trace(trace_token)
                if trace_token is not None and hasattr(model_client, "end_trace")
                else []
            )
            provenance = await self.inference_provenance(settings, trace)
            with self.write_guard, self.db.session() as session:
                record = get(session, RelationImpactAnalysis, record_id)
                delivery = get(session, OrganizationRelationCandidate, organization_candidate_id)
                record.result = result
                record.coverage = coverage
                record.status = status
                record.error = error
                record.provenance = provenance
                record.analysis_plan = relation_ai.complete_analysis_plan(
                    context["plan"],
                    status=status,
                    coverage=coverage,
                    provenance=provenance,
                    result_url=f"/impact?candidate={organization_candidate_id}",
                )
                delivery.status = "analysed" if status == "succeeded" else "pending"
                delivery.updated_at = utcnow()
                session.commit()
                return self._relation_analysis_dict(record, cached=False)

    def relation_analysis_history(self, organization_candidate_id: str) -> dict:
        with self.db.session() as session:
            get(session, OrganizationRelationCandidate, organization_candidate_id)
            records = list(
                session.scalars(
                    select(RelationImpactAnalysis)
                    .where(
                        RelationImpactAnalysis.organization_candidate_id
                        == organization_candidate_id
                    )
                    .order_by(RelationImpactAnalysis.created_at.desc())
                )
            )
            items = [self._relation_analysis_dict(record) for record in records]
            current = next((item for item in items if item["status"] == "succeeded"
                            and not item["stale"]), None)
            return {
                "items": items,
                "total": len(records),
                "current": current,
                "latest_attempt": items[0] if items else None,
            }

    def relation_analysis_evidence(self, analysis_id: str, evidence_id: str) -> dict:
        with self.db.session() as session:
            record = get(session, RelationImpactAnalysis, analysis_id)
            row = next(
                (item for item in record.evidence_json or [] if item.get("evidence_id") == evidence_id),
                None,
            )
            if not row:
                raise DomainError("The cited relation evidence was not found.", 404, "not_found")
            return row

    def enqueue_analysis(
        self, comparison_id: str, output_locale: str = ai.DEFAULT_OUTPUT_LOCALE
    ):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            profile = get(session, Profile, self.tenant_record_id)
            key = ai.cache_key(
                comparison, profile, self.settings, self.prompt_settings, output_locale
            )
            plan, _ = ai.build_impact_plan(
                self.settings,
                comparison,
                old,
                new,
                profile,
                output_locale=output_locale,
            )
            group_total = max(1, int(plan["execution"]["batch_count"]))
            job, reused = durable_jobs.enqueue(
                session,
                job_type="impact_analysis",
                target_type="comparison",
                target_id=comparison_id,
                queue="ai_background",
                idempotency_key=f"impact:{key}",
                payload={"comparison_id": comparison_id, "output_locale": output_locale},
                progress_total=3,
                max_attempts=self.settings.job_max_attempts,
                steps=[
                    ("Prepare material changes", {"comparison_id": comparison_id}),
                    (
                        "Analyse evidence groups",
                        {"stage": "analysing", "group_total": group_total},
                    ),
                    ("Validate evidence and save report", {"stage": "validating"}),
                ],
            )
            if reused and job.state in {"failed", "cancelled"}:
                job = durable_jobs.retry(session, job.id)
            inference_step = session.scalar(
                select(JobStep).where(JobStep.job_id == job.id, JobStep.position == 2)
            )
            if inference_step and inference_step.state == "pending":
                inference_step.progress_total = group_total
            session.commit()
            return durable_jobs.serialize(session, job)

    def enqueue_ask(
        self,
        comparison_id: str,
        question: str,
        history: list[dict],
        output_locale: str | None = None,
    ):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            profile = get(session, Profile, self.tenant_record_id)
            impact_report = self.current_impact_report(
                session,
                comparison,
                profile,
                self.settings,
                self.prompt_settings,
                output_locale,
            )
            key = ai.ask_cache_key(
                comparison,
                profile,
                self.settings,
                self.prompt_settings,
                question,
                history,
                impact_report,
                output_locale,
            )
            job, reused = durable_jobs.enqueue(
                session,
                job_type="ask",
                target_type="comparison",
                target_id=comparison_id,
                queue="ai_interactive",
                priority=8,
                idempotency_key=f"ask:{key}",
                payload={
                    "comparison_id": comparison_id,
                    "question": question.strip(),
                    "history": history[-4:],
                    "output_locale": output_locale,
                },
                progress_total=3,
                max_attempts=self.settings.job_max_attempts,
                steps=[
                    ("Select saved evidence", {"comparison_id": comparison_id}),
                    ("Generate cited answer", {}),
                    ("Validate and save answer", {}),
                ],
            )
            if reused and job.state in {"failed", "cancelled"}:
                job = durable_jobs.retry(session, job.id)
            reused_completed = reused and job.state == "succeeded"
            if reused_completed and job.result_id:
                record = session.get(AskRecord, job.result_id)
                if record:
                    record.use_count += 1
                    record.last_used_at = utcnow()
            session.commit()
            serialized = durable_jobs.serialize(session, job)
            if reused_completed and serialized.get("result"):
                serialized["result"]["data"] = {
                    **(serialized["result"].get("data") or {}),
                    "cached": True,
                }
            return serialized

    @staticmethod
    def current_impact_report(
        session: Session,
        comparison: Comparison,
        profile: Profile,
        settings,
        prompts,
        output_locale: str | None = None,
    ) -> dict | None:
        current_key = ai.cache_key(
            comparison, profile, settings, prompts, output_locale or ai.DEFAULT_OUTPUT_LOCALE
        )
        record = session.scalar(
            select(Analysis)
            .where(
                Analysis.comparison_id == comparison.id,
                Analysis.cache_key == current_key,
                Analysis.status == "succeeded",
            )
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        if not record or (record.result or {}).get("schema_version") != ai.IMPACT_REPORT_SCHEMA_VERSION:
            return None
        return {"id": record.id, "result": record.result}

    async def analyse(
        self,
        comparison_id: str,
        progress_callback=None,
        output_locale: str = ai.DEFAULT_OUTPUT_LOCALE,
    ):
        lock = self.analysis_locks.setdefault(comparison_id, asyncio.Lock())
        async with lock:
            settings, model_client = self.settings, self.model_client
            prompts = self.prompt_settings.model_copy(deep=True)
            prompt_revision = self.prompt_revision
            with self.write_guard, self.db.session() as session:
                comparison = get(session, Comparison, comparison_id)
                old, new = (
                    get(session, Version, comparison.old_version_id),
                    get(session, Version, comparison.new_version_id),
                )
                if self.ensure_complete_diff(session, comparison, old, new):
                    session.commit()
                if not comparison.diff["changed"]:
                    raise DomainError(
                        "These versions have no text changes to analyse. You can still ask about their content."
                    )
                profile = get(session, Profile, self.tenant_record_id)
                identity = self.refresh_comparison_identity(session, comparison)
                if identity["effective_status"] in {"mismatch", "unknown"}:
                    raise DomainError(
                        "AI analysis is paused until both artifacts are assigned to the same legal work. Attach the correct version or confirm an unknown assignment first.",
                        409,
                        f"document_identity_{identity['effective_status']}",
                    )
                key = ai.cache_key(comparison, profile, settings, prompts, output_locale)
                cached = session.scalar(
                    select(Analysis)
                    .where(Analysis.cache_key == key, Analysis.status == "succeeded")
                    .order_by(Analysis.created_at.desc())
                    .limit(1)
                )
                if cached:
                    cached.use_count += 1
                    cached.last_used_at = utcnow()
                    session.commit()
                    return {**as_dict(cached), "cached": True, "stale": False}
                analysis_plan, prepared = ai.build_impact_plan(
                    settings,
                    comparison,
                    old,
                    new,
                    profile,
                    output_locale=output_locale,
                )
                if (
                    analysis_plan["estimates"]["planned_generation_calls"]
                    and not settings.model_configured
                ):
                    raise DomainError(
                        "Apertus is not connected. Open Settings to configure its endpoint and model.",
                        503,
                        "model_not_configured",
                    )
                record = Analysis(
                    comparison_id=comparison.id,
                    cache_key=key,
                    model=settings.apertus_model,
                    prompt_revision=prompt_revision,
                    analysis_plan=analysis_plan,
                    last_used_at=utcnow(),
                )
                session.add(record)
                session.commit()
                record_id = record.id
            with correlation_context(comparison_id=comparison.id, analysis_id=record_id):
                trace_token = (
                    model_client.begin_trace("background")
                    if hasattr(model_client, "begin_trace")
                    else None
                )
                try:
                    result, coverage = await ai.impact_analysis(
                        model_client,
                        settings,
                        comparison,
                        old,
                        new,
                        profile,
                        prompts,
                        prepared,
                        progress_callback,
                        output_locale,
                    )
                    status, error = "succeeded", None
                except Exception as exc:
                    result, coverage, status = None, {}, "failed"
                    error = (
                        exc.message
                        if isinstance(exc, DomainError)
                        else "Apertus analysis failed. The saved comparison remains available."
                    )
                    if not isinstance(exc, DomainError):
                        logger.exception("Model analysis failed")
                trace = (
                    model_client.end_trace(trace_token)
                    if trace_token is not None and hasattr(model_client, "end_trace")
                    else []
                )
                provenance = await self.inference_provenance(settings, trace)
            with self.write_guard, self.db.session() as session:
                record = get(session, Analysis, record_id)
                record.result, record.coverage, record.status, record.error = result, coverage, status, error
                record.provenance = provenance
                record.analysis_plan = ai.complete_analysis_plan(
                    analysis_plan,
                    status=status,
                    coverage=coverage,
                    provenance=provenance,
                    result_url=f"/compare/{comparison.id}",
                )
                session.commit()
                return {
                    **as_dict(record),
                    "cached": False,
                    "stale": key
                    != ai.cache_key(
                        comparison,
                        get(session, Profile, self.tenant_record_id),
                        self.settings,
                        self.prompt_settings,
                        output_locale,
                    ),
                }

    async def ask(
        self,
        comparison_id: str,
        question: str,
        history: list[dict],
        output_locale: str | None = None,
        progress_callback=None,
    ):
        settings, model_client = self.settings, self.model_client
        prompts = self.prompt_settings.model_copy(deep=True)
        prompt_revision = self.prompt_revision
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            if self.ensure_complete_diff(session, comparison, old, new):
                session.commit()
            profile = get(session, Profile, self.tenant_record_id)
            identity = self.refresh_comparison_identity(session, comparison)
            if identity["effective_status"] in {"mismatch", "unknown"}:
                raise DomainError(
                    "Ask is paused until both artifacts are assigned to the same legal work. Attach the correct version or confirm an unknown assignment first.",
                    409,
                    f"document_identity_{identity['effective_status']}",
                )
            impact_report = self.current_impact_report(
                session, comparison, profile, settings, prompts, output_locale
            )
            key = ai.ask_cache_key(
                comparison,
                profile,
                settings,
                prompts,
                question,
                history,
                impact_report,
                output_locale,
            )
            analysis_plan = ai.build_ask_plan(
                settings,
                comparison,
                old,
                new,
                question,
                prompts,
                profile,
                history,
                impact_report,
                output_locale,
            )
        if progress_callback:
            await progress_callback("evidence_selected")
        lock_key = comparison_id + ":" + key
        lock = self.ask_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            with self.write_guard, self.db.session() as session:
                cached = session.scalar(
                    select(AskRecord)
                    .where(AskRecord.cache_key == key, AskRecord.status == "succeeded")
                    .order_by(AskRecord.created_at.desc())
                    .limit(1)
                )
                if cached:
                    cached.use_count += 1
                    cached.last_used_at = utcnow()
                    session.commit()
                    return self.ask_result(cached, cached=True)
                record = session.scalar(
                    select(AskRecord)
                    .where(AskRecord.cache_key == key)
                    .order_by(AskRecord.created_at.desc())
                    .limit(1)
                )
                if record:
                    record.status = "pending"
                    record.error = None
                    record.result = {}
                    record.coverage = {}
                    record.provenance = {}
                    record.analysis_plan = analysis_plan
                    record.last_used_at = utcnow()
                else:
                    record = AskRecord(
                        comparison_id=comparison_id,
                        cache_key=key,
                        question=question.strip(),
                        history=history[-4:],
                        model=settings.apertus_model,
                        prompt_revision=prompt_revision,
                        context_mode=prompts.ask_context_mode,
                        analysis_plan=analysis_plan,
                        last_used_at=utcnow(),
                    )
                    session.add(record)
                session.commit()
                record_id = record.id
            with correlation_context(comparison_id=comparison.id, ask_record_id=record_id):
                trace_token = (
                    model_client.begin_trace("interactive")
                    if hasattr(model_client, "begin_trace")
                    else None
                )
                try:
                    result = await ai.answer_question(
                        model_client,
                        settings,
                        comparison,
                        old,
                        new,
                        profile,
                        question,
                        history,
                        prompts,
                        impact_report,
                        output_locale,
                    )
                    if progress_callback:
                        await progress_callback("generated")
                except Exception as exc:
                    trace = (
                        model_client.end_trace(trace_token)
                        if trace_token is not None and hasattr(model_client, "end_trace")
                        else []
                    )
                    provenance = await self.inference_provenance(settings, trace)
                    message = (
                        exc.message
                        if isinstance(exc, DomainError)
                        else "Apertus could not answer this question. The question was saved for review."
                    )
                    with self.write_guard, self.db.session() as session:
                        record = get(session, AskRecord, record_id)
                        record.status, record.error = "failed", message
                        record.provenance = provenance
                        record.analysis_plan = ai.complete_analysis_plan(
                            analysis_plan,
                            status="failed",
                            coverage={},
                            provenance=provenance,
                            result_url=f"/compare/{comparison.id}",
                        )
                        session.commit()
                    if isinstance(exc, DomainError):
                        raise
                    logger.exception("Model question failed")
                    raise DomainError(message, 502, "model_error") from exc
                trace = (
                    model_client.end_trace(trace_token)
                    if trace_token is not None and hasattr(model_client, "end_trace")
                    else []
                )
                provenance = await self.inference_provenance(settings, trace)
            coverage = result.get("coverage") or {}
            stored_result = {
                key: value
                for key, value in result.items()
                if key not in {"coverage", "model"}
            }
            with self.write_guard, self.db.session() as session:
                record = get(session, AskRecord, record_id)
                record.status = "succeeded"
                record.result = stored_result
                record.coverage = coverage
                record.provenance = provenance
                record.analysis_plan = ai.complete_analysis_plan(
                    analysis_plan,
                    status="succeeded",
                    coverage=coverage,
                    provenance=provenance,
                    result_url=f"/compare/{comparison.id}",
                )
                record.context_mode = result.get("context_mode", prompts.ask_context_mode)
                record.error = None
                session.commit()
                return self.ask_result(record, cached=False)

    @staticmethod
    def ask_result(record: AskRecord, *, cached: bool) -> dict:
        return {
            **(record.result or {}),
            "coverage": record.coverage or {},
            "provenance": record.provenance or {},
            "analysis_plan": record.analysis_plan or {},
            "model": record.model,
            "record_id": record.id,
            "cached": cached,
            "created_at": (
                record.created_at.replace(tzinfo=UTC).isoformat()
                if record.created_at.tzinfo is None
                else record.created_at.isoformat()
            ),
            "last_used_at": (
                record.last_used_at.replace(tzinfo=UTC).isoformat()
                if record.last_used_at and record.last_used_at.tzinfo is None
                else record.last_used_at.isoformat()
                if record.last_used_at
                else None
            ),
            "use_count": record.use_count,
            "prompt_revision": record.prompt_revision,
        }

    def ai_history(
        self,
        *,
        law_id: str | None = None,
        comparison_id: str | None = None,
        limit: int = 100,
    ):
        with self.db.session() as session:
            if comparison_id:
                comparison = get(session, Comparison, comparison_id)
                if law_id and comparison.law_id != law_id:
                    raise DomainError("The comparison does not belong to this document.")
                comparisons = [comparison]
            else:
                if not law_id:
                    raise DomainError("Choose a document or comparison for AI history.")
                get(session, Law, law_id)
                comparisons = list(
                    session.scalars(
                        select(Comparison)
                        .where(Comparison.law_id == law_id)
                        .order_by(Comparison.created_at.desc())
                    )
                )
            comparison_ids = [comparison.id for comparison in comparisons]
            if not comparison_ids:
                return {"items": [], "total": 0}
            comparison_map = {comparison.id: comparison for comparison in comparisons}
            version_ids = {
                version_id
                for comparison in comparisons
                for version_id in (comparison.old_version_id, comparison.new_version_id)
            }
            versions = {
                version.id: version
                for version in session.scalars(select(Version).where(Version.id.in_(version_ids)))
            }

            def comparison_summary(item_id: str):
                comparison = comparison_map[item_id]
                old, new = versions[comparison.old_version_id], versions[comparison.new_version_id]

                def side(version: Version):
                    return {
                        "id": version.id,
                        "title": version.title,
                        "declared_date": version.declared_date,
                        "origin": version.origin,
                        "created_at": (
                            version.created_at.replace(tzinfo=UTC).isoformat()
                            if version.created_at.tzinfo is None
                            else version.created_at.isoformat()
                        ),
                        "artifact_url": f"/api/versions/{version.id}/artifact",
                    }

                return {
                    "id": comparison.id,
                    "mode": comparison.mode,
                    "created_at": (
                        comparison.created_at.replace(tzinfo=UTC).isoformat()
                        if comparison.created_at.tzinfo is None
                        else comparison.created_at.isoformat()
                    ),
                    "before": side(old),
                    "after": side(new),
                    "counts": comparison.diff.get("counts", {}),
                }

            analyses = list(
                session.scalars(
                    select(Analysis).where(Analysis.comparison_id.in_(comparison_ids))
                )
            )
            questions = list(
                session.scalars(
                    select(AskRecord).where(AskRecord.comparison_id.in_(comparison_ids))
                )
            )
            items = [
                {
                    "type": "impact",
                    **as_dict(record, {"cache_key"}),
                    "comparison": comparison_summary(record.comparison_id),
                }
                for record in analyses
            ]
            items.extend(
                {
                    "type": "question",
                    **as_dict(record, {"cache_key"}),
                    "comparison": comparison_summary(record.comparison_id),
                }
                for record in questions
            )
            items.sort(key=lambda item: item["created_at"], reverse=True)
            return {"items": items[:limit], "total": len(items)}
