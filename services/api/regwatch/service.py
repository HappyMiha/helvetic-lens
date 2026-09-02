import asyncio
import hashlib
import logging
import threading
import time
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from . import analysis as ai
from .config import DomainError, Settings
from .db import Database, utcnow
from .diffing import DIFF_SCHEMA_VERSION, compare_passages
from .extraction import Extracted, Fetcher, canonical_url, discover_links, extract
from .integration_logs import IntegrationLogger
from .model_settings import ApertusSettingsInput, public_settings, resolve_key, resolved_settings
from .models import (
    Analysis,
    ApertusConfiguration,
    AskRecord,
    Comparison,
    IntegrationLog,
    Law,
    Observation,
    Profile,
    PromptConfiguration,
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


class RegWatch:
    def __init__(self, settings: Settings, fetcher=None, model_client=None):
        self.settings = settings
        self.environment_settings = settings.model_copy(deep=True)
        self.db = Database(settings)
        self.integration_logger = IntegrationLogger(self.db.session)
        self.fetcher = fetcher or Fetcher(settings, self.integration_logger)
        self.model_client = model_client or ai.ModelClient(settings, self.integration_logger)
        self.prompt_settings = default_prompt_settings()
        self.prompt_revision = 1
        self.write_guard = threading.RLock()
        self.analysis_locks: dict[str, asyncio.Lock] = {}
        self.ask_locks: dict[str, asyncio.Lock] = {}

    def initialize(self):
        self.db.migrate()
        with self.db.session() as session:
            if not session.get(Profile, "default"):
                session.add(Profile(id="default"))
            for scan in session.scalars(select(Scan).where(Scan.status.in_(["queued", "running"]))):
                scan.status, scan.finished_at = "interrupted", utcnow()
                for item in session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)):
                    if item.stage not in {"complete", "failed"}:
                        item.stage, item.error = (
                            "interrupted",
                            "The API restarted before this item completed. Retry the scan.",
                        )
                        if item.analysis_status == "pending":
                            item.analysis_status = "interrupted"
            for analysis in session.scalars(select(Analysis).where(Analysis.status == "pending")):
                analysis.status, analysis.error = (
                    "failed",
                    "Analysis was interrupted by a service restart. Retry it.",
                )
            for record in session.scalars(select(AskRecord).where(AskRecord.status == "pending")):
                record.status, record.error = (
                    "failed",
                    "The question was interrupted by a service restart. Ask it again to retry.",
                )
            session.commit()
            saved = session.get(ApertusConfiguration, "default")
            if saved:
                self.apply_model_settings(resolved_settings(self.environment_settings, saved))
            prompt_record = session.get(PromptConfiguration, "default")
            self.prompt_settings = resolved_prompt_settings(prompt_record)
            self.prompt_revision = prompt_record.revision if prompt_record else 1

    def apply_model_settings(self, settings: Settings):
        self.settings = settings
        if isinstance(self.model_client, ai.ModelClient):
            self.model_client = ai.ModelClient(settings, self.integration_logger)

    def apertus_configuration(self):
        with self.db.session() as session:
            saved = session.get(ApertusConfiguration, "default")
            return public_settings(self.settings, saved)

    def save_model_settings(self, data: ApertusSettingsInput):
        with self.write_guard, self.db.session() as session:
            saved = session.get(ApertusConfiguration, "default")
            next_settings = resolved_settings(self.environment_settings, saved, data)
            key_source, stored_key, _ = resolve_key(self.environment_settings, saved, data)
            if saved is None:
                saved = ApertusConfiguration(id="default")
                session.add(saved)
            saved.values = data.public_values()
            saved.key_source, saved.api_key = key_source, stored_key
            saved.updated_at = utcnow()
            session.commit()
            self.apply_model_settings(next_settings)
            return public_settings(self.settings, saved)

    def reset_model_settings(self):
        with self.write_guard, self.db.session() as session:
            saved = session.get(ApertusConfiguration, "default")
            if saved:
                session.delete(saved)
                session.commit()
            self.apply_model_settings(self.environment_settings.model_copy(deep=True))
            return public_settings(self.settings, None)

    def prompt_configuration(self):
        with self.db.session() as session:
            record = session.get(PromptConfiguration, "default")
            return public_prompt_settings(self.prompt_settings, record)

    def save_prompt_settings(self, data: PromptSettingsInput):
        with self.write_guard, self.db.session() as session:
            record = session.get(PromptConfiguration, "default")
            if record is None:
                record = PromptConfiguration(id="default", revision=1)
                session.add(record)
            else:
                record.revision += 1
            record.values = data.model_dump()
            record.updated_at = utcnow()
            session.commit()
            self.prompt_settings = data.model_copy(deep=True)
            self.prompt_revision = record.revision
            return public_prompt_settings(self.prompt_settings, record)

    def reset_prompt_settings(self):
        with self.write_guard, self.db.session() as session:
            record = session.get(PromptConfiguration, "default")
            if record:
                session.delete(record)
                session.commit()
            self.prompt_settings = default_prompt_settings()
            self.prompt_revision = 1
            return public_prompt_settings(self.prompt_settings, None)

    async def test_model_settings(self, data: ApertusSettingsInput | None = None):
        if data is not None:
            with self.db.session() as session:
                saved = session.get(ApertusConfiguration, "default")
                settings = resolved_settings(self.environment_settings, saved, data)
            model_client = ai.ModelClient(settings, self.integration_logger)
        else:
            settings, model_client = self.settings, self.model_client
        start = time.monotonic()
        reply = await model_client.complete(
            "Return only a JSON object with a status field equal to ok.", "Test the RegWatch connection."
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
            saved = session.get(ApertusConfiguration, "default")
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
        version = session.scalar(
            select(Version).where(
                Version.law_id == law.id,
                Version.content_hash == document.content_hash,
                Version.extractor == document.extractor,
            )
        )
        reused = version is not None
        if version is None:
            version = Version(
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

    def ensure_comparison(self, session: Session, old: Version, new: Version, mode: str) -> Comparison:
        if old.law_id != new.law_id:
            raise DomainError("Both versions must belong to the same law.")
        existing = session.scalar(
            select(Comparison).where(
                Comparison.old_version_id == old.id,
                Comparison.new_version_id == new.id,
                Comparison.mode == mode,
            )
        )
        if existing:
            self.ensure_complete_diff(session, existing, old, new)
            return existing
        comparison = Comparison(
            law_id=old.law_id,
            old_version_id=old.id,
            new_version_id=new.id,
            mode=mode,
            diff=compare_passages(old.passages, new.passages),
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
            tracked = set(session.scalars(select(Law.url)))
            for candidate in result["candidates"]:
                candidate["tracked"] = candidate["url"] in tracked
            source.discovery, source.last_checked, source.error = result, utcnow(), None
            session.commit()
        return result

    async def add_law(self, data: dict):
        url = canonical_url(data["url"])
        provider = data.get("provider", "native")
        with self.db.session() as session:
            existing = session.scalar(select(Law).where(Law.url == url))
            if existing:
                raise DomainError(
                    f"This document is already tracked as '{existing.name}'.", 409, "duplicate_law"
                )
            if data.get("source_id"):
                get(session, Source, data["source_id"])
        fetched = await self.fetcher.fetch(url, provider)
        name = PurePosixPath(urlsplit(fetched.url).path).name or "document.html"
        document = await asyncio.to_thread(extract, fetched.body, fetched.content_type, name, provider)
        with self.write_guard, self.db.session() as session:
            if session.scalar(select(Law.id).where(Law.url == url)):
                raise DomainError("This document was already added.", 409, "duplicate_law")
            law = Law(
                name=data.get("name") or document.title[:300],
                url=url,
                source_id=data.get("source_id"),
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
            session.commit()
            return self.law_summary(session, law)

    def law_summary(self, session: Session, law: Law):
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
            **as_dict(law),
            "current_version": version_summary(current) if current else None,
            "comparison_id": comparison.id if comparison else None,
            "comparison_mode": comparison.mode if comparison else None,
            "change_counts": comparison.diff["counts"] if comparison else None,
            "analysis": analysis,
        }

    def law_detail(self, law_id: str):
        with self.db.session() as session:
            law = get(session, Law, law_id)
            return {
                **self.law_summary(session, law),
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
            if comparison_ids:
                session.execute(
                    delete(AskRecord).where(AskRecord.comparison_id.in_(comparison_ids))
                )
                session.execute(delete(Analysis).where(Analysis.comparison_id.in_(comparison_ids)))
            session.execute(delete(ScanItem).where(ScanItem.law_id == law_id))
            session.execute(delete(Comparison).where(Comparison.law_id == law_id))
            session.execute(delete(Observation).where(Observation.law_id == law_id))
            session.execute(delete(Version).where(Version.law_id == law_id))
            name = law.name
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
    ):
        with self.db.session() as session:
            get(session, Law, law_id)
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
        if preview:
            return document.preview()
        with self.write_guard, self.db.session() as session:
            law = get(session, Law, law_id)
            version, reused = self.save_snapshot(
                session, law, document, origin, source_url, declared_date or None, synthetic, metadata
            )
            session.commit()
            return {
                "version": version_summary(version),
                "reused": reused,
                "current_version_id": law.current_version_id,
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
        profile = get(session, Profile, "default")
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
            if self.ensure_complete_diff(session, comparison, old, new):
                session.commit()
            law = get(session, Law, comparison.law_id)
            return {
                **as_dict(comparison),
                "old_version": version_summary(old),
                "new_version": version_summary(new),
                "law": as_dict(law),
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
            laws = (
                list(session.scalars(select(Law).where(Law.active.is_(True))))
                if law_ids is None
                else [get(session, Law, law_id) for law_id in dict.fromkeys(law_ids)]
            )
            if not laws:
                raise DomainError("Add or select an active law before scanning.")
            if len(laws) > 25:
                raise DomainError("The MVP supports at most 25 documents per scan. Select a smaller batch.")
            if baseline_id and len(laws) != 1:
                raise DomainError("Choose a historical baseline for one law at a time.")
            if any(not law.active for law in laws):
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
            for law in laws:
                session.add(
                    ScanItem(
                        scan_id=scan.id,
                        law_id=law.id,
                        baseline_version_id=baseline_id or law.current_version_id,
                        mode="historical" if baseline_id else "monitoring",
                        events=[{"stage": "queued", "at": utcnow().isoformat()}],
                    )
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

    async def run_scan(self, scan_id: str):
        with self.db.session() as session:
            scan = get(session, Scan, scan_id)
            scan.status = "running"
            ids = list(session.scalars(select(ScanItem.id).where(ScanItem.scan_id == scan_id)))
            session.commit()
        for item_id in ids:
            try:
                await self.run_scan_item(item_id)
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
                    law = get(session, Law, item.law_id)
                    law.last_result, law.last_error, law.last_checked = "failed", message, utcnow()
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
            law.current_version_id, law.last_checked = version.id, utcnow()
            law.last_result, law.last_error = item.live_result, None
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
            return {
                **as_dict(scan),
                "completed": sum(i["stage"] in {"complete", "failed", "interrupted"} for i in items),
                "items": items,
            }

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
            result = session.execute(delete(IntegrationLog))
            session.commit()
            return {"deleted": result.rowcount or 0}

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
                profile = get(session, Profile, "default")
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
            with self.write_guard, self.db.session() as session:
                record = get(session, Analysis, record_id)
                record.result, record.coverage, record.status, record.error = result, coverage, status, error
                session.commit()
                return {
                    **as_dict(record),
                    "cached": False,
                    "stale": key
                    != ai.cache_key(
                        comparison,
                        get(session, Profile, "default"),
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
            profile = get(session, Profile, "default")
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
                message = (
                    exc.message
                    if isinstance(exc, DomainError)
                    else "Apertus could not answer this question. The question was saved for review."
                )
                with self.write_guard, self.db.session() as session:
                    record = get(session, AskRecord, record_id)
                    record.status, record.error = "failed", message
                    session.commit()
                if isinstance(exc, DomainError):
                    raise
                logger.exception("Model question failed")
                raise DomainError(message, 502, "model_error") from exc
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
                record.context_mode = result.get("context_mode", prompts.ask_context_mode)
                record.error = None
                session.commit()
                return self.ask_result(record, cached=False)

    @staticmethod
    def ask_result(record: AskRecord, *, cached: bool) -> dict:
        return {
            **(record.result or {}),
            "coverage": record.coverage or {},
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
