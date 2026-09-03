import asyncio
import hashlib
import logging
import threading
import time
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from sqlalchemy import delete, func, inspect, or_, select
from sqlalchemy.orm import Session

from . import analysis as ai
from . import jobs as durable_jobs
from .config import DomainError, Settings
from .db import Database, utcnow
from .diffing import DIFF_SCHEMA_VERSION, compare_passages
from .extraction import (
    Extracted,
    Fetcher,
    canonical_url,
    discover_links,
    extract,
    fedlex_eli_reference,
)
from .identity import (
    IDENTITY_REVISION,
    assess_comparison_identity,
    assess_document_identity,
    build_artifact_identity,
)
from .integration_logs import IntegrationLogger
from .model_manager_client import ModelManagerClient
from .model_settings import ApertusSettingsInput, public_settings, resolve_key, resolved_settings
from .models import (
    LEGACY_ORGANIZATION_ID,
    Analysis,
    ApertusConfiguration,
    AskRecord,
    Comparison,
    DocumentWatch,
    IdentityDecision,
    IntegrationLog,
    Job,
    JobStep,
    Law,
    Observation,
    Organization,
    OrganizationQuota,
    OutboxMessage,
    Profile,
    PromptConfiguration,
    PromptRevision,
    Scan,
    ScanItem,
    Source,
    Version,
)
from .prompt_settings import (
    PromptSettingsInput,
    default_prompt_settings,
    public_prompt_settings,
    resolved_prompt_settings,
)

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
        self.settings = settings
        self.environment_settings = settings.model_copy(deep=True)
        self.organization_id = organization_id
        self.organization_name = organization_name
        self.db = Database(settings, organization_id)
        self.integration_logger = IntegrationLogger(self.db.session)
        self.fetcher = fetcher or Fetcher(settings, self.integration_logger)
        self.model_client = model_client or ai.ModelClient(settings, self.integration_logger)
        self.model_manager = model_manager_client or ModelManagerClient(settings)
        self.prompt_settings = default_prompt_settings()
        self.prompt_revision = 1
        self.write_guard = threading.RLock()
        self.analysis_locks: dict[str, asyncio.Lock] = {}
        self.ask_locks: dict[str, asyncio.Lock] = {}

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
                self.apply_model_settings(resolved_settings(self.environment_settings, saved))
            prompt_record = session.get(PromptConfiguration, self.tenant_record_id)
            self.prompt_settings = resolved_prompt_settings(prompt_record)
            self.prompt_revision = prompt_record.revision if prompt_record else 1
            for version in session.scalars(select(Version)):
                law = session.get(Law, version.law_id)
                if law:
                    self.refresh_version_identity(session, law, version)
            for comparison in session.scalars(select(Comparison)):
                self.refresh_comparison_identity(session, comparison)
            session.commit()

    def apply_model_settings(self, settings: Settings):
        self.settings = settings
        if isinstance(self.model_client, ai.ModelClient):
            self.model_client = ai.ModelClient(settings, self.integration_logger)

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
            next_settings = resolved_settings(self.environment_settings, saved, data)
            key_source, stored_key, _ = resolve_key(self.environment_settings, saved, data)
            if saved is None:
                saved = ApertusConfiguration(id=self.tenant_record_id)
                session.add(saved)
            saved.values = data.public_values()
            saved.key_source, saved.api_key = key_source, stored_key
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
            return public_prompt_settings(self.prompt_settings, record)

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
            return public_prompt_settings(self.prompt_settings, record)

    def reset_prompt_settings(self):
        with self.write_guard, self.db.session() as session:
            record = session.get(PromptConfiguration, self.tenant_record_id)
            if record:
                session.delete(record)
                session.commit()
            self.prompt_settings = default_prompt_settings()
            self.prompt_revision = 1
            return public_prompt_settings(self.prompt_settings, None)

    async def test_model_settings(self, data: ApertusSettingsInput | None = None):
        if data is not None:
            with self.db.session() as session:
                saved = session.get(ApertusConfiguration, self.tenant_record_id)
                settings = resolved_settings(self.environment_settings, saved, data)
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
            settings = resolved_settings(self.environment_settings, saved, data)
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
            diff=compare_passages(old.passages, new.passages),
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
        comparison.diff = compare_passages(old.passages, new.passages)
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

    def latest_analysis(self, session: Session, comparison: Comparison):
        analysis = session.scalar(
            select(Analysis)
            .where(Analysis.comparison_id == comparison.id)
            .order_by(Analysis.last_used_at.desc().nullslast(), Analysis.created_at.desc())
            .limit(1)
        )
        if not analysis:
            return None
        profile = get(session, Profile, self.tenant_record_id)
        return {
            **as_dict(analysis),
            "stale": analysis.cache_key
            != ai.cache_key(comparison, profile, self.settings, self.prompt_settings),
        }

    def comparison_detail(self, comparison_id: str):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            law = get(session, Law, comparison.law_id)
            identity = self.refresh_comparison_identity(session, comparison)
            session.commit()
            return {
                **as_dict(comparison),
                "old_version": version_summary(old),
                "new_version": version_summary(new),
                "law": as_dict(law),
                "identity": identity,
                "analysis": self.latest_analysis(session, comparison),
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

    def jobs(self, limit: int = 50):
        with self.db.session() as session:
            records = list(
                session.scalars(select(Job).order_by(Job.created_at.desc()).limit(max(1, min(200, limit))))
            )
            return [durable_jobs.serialize(session, record) for record in records]

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
            job_type in {"impact_analysis", "ask"}
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
                mark(1, 2, "running")
                result_json = await self.analyse(target_id)
                if result_json.get("status") != "succeeded":
                    raise DomainError(
                        result_json.get("error") or "The impact analysis failed.",
                        502,
                        "analysis_failed",
                    )
                mark(2, 2, "succeeded")
                mark(3, 3, "succeeded")
                result_type = "analysis"
                result_id = result_json["id"]
                result_url = f"/compare/{target_id}#impact"
            elif job_type == "ask":
                mark(1, 1, "succeeded")
                mark(1, 2, "running")
                result_json = await self.ask(
                    target_id,
                    payload.get("question", ""),
                    payload.get("history", []),
                )
                mark(2, 2, "succeeded")
                mark(3, 3, "succeeded")
                result_type = "answer"
                result_id = result_json["record_id"]
                result_url = f"/compare/{target_id}#ask"
            elif job_type in {"model_download", "model_start"}:
                action = job_type.removeprefix("model_")
                result_json = await self._run_model_job(job_id, target_id, action, payload, worker)
                result_type, result_id, result_url = "local_model", target_id, "/models"
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
                durable_jobs.fail(session, job_id, code=code, detail=detail)
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

    def enqueue_analysis(self, comparison_id: str):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            profile = get(session, Profile, self.tenant_record_id)
            key = ai.cache_key(comparison, profile, self.settings, self.prompt_settings)
            job, _ = durable_jobs.enqueue(
                session,
                job_type="impact_analysis",
                target_type="comparison",
                target_id=comparison_id,
                queue="ai_background",
                idempotency_key=f"impact:{key}",
                payload={"comparison_id": comparison_id},
                progress_total=3,
                max_attempts=self.settings.job_max_attempts,
                steps=[
                    ("Prepare material changes", {"comparison_id": comparison_id}),
                    ("Run local inference", {}),
                    ("Validate and save result", {}),
                ],
            )
            session.commit()
            return durable_jobs.serialize(session, job)

    def enqueue_ask(self, comparison_id: str, question: str, history: list[dict]):
        with self.write_guard, self.db.session() as session:
            comparison = get(session, Comparison, comparison_id)
            old, new = (
                get(session, Version, comparison.old_version_id),
                get(session, Version, comparison.new_version_id),
            )
            self.ensure_complete_diff(session, comparison, old, new)
            profile = get(session, Profile, self.tenant_record_id)
            key = ai.ask_cache_key(
                comparison,
                profile,
                self.settings,
                self.prompt_settings,
                question,
                history,
            )
            job, _ = durable_jobs.enqueue(
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
                },
                progress_total=3,
                max_attempts=self.settings.job_max_attempts,
                steps=[
                    ("Prepare cited evidence", {"comparison_id": comparison_id}),
                    ("Run local inference", {}),
                    ("Validate and save answer", {}),
                ],
            )
            session.commit()
            return durable_jobs.serialize(session, job)

    async def analyse(self, comparison_id: str):
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
                key = ai.cache_key(comparison, profile, settings, prompts)
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
                if not settings.model_configured:
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
                    last_used_at=utcnow(),
                )
                session.add(record)
                session.commit()
                record_id = record.id
            trace_token = (
                model_client.begin_trace("background")
                if hasattr(model_client, "begin_trace")
                else None
            )
            try:
                result, coverage = await ai.impact_analysis(
                    model_client, settings, comparison, old, new, profile, prompts
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
                    ),
                }

    async def ask(self, comparison_id: str, question: str, history: list[dict]):
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
            key = ai.ask_cache_key(
                comparison, profile, settings, prompts, question, history
            )
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
                record = AskRecord(
                    comparison_id=comparison_id,
                    cache_key=key,
                    question=question.strip(),
                    history=history[-4:],
                    model=settings.apertus_model,
                    prompt_revision=prompt_revision,
                    context_mode=prompts.ask_context_mode,
                    last_used_at=utcnow(),
                )
                session.add(record)
                session.commit()
                record_id = record.id
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
                )
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
