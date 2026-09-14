"""Worker-only public evidence ingestion; no authentication or delivery side effects."""

import re
from datetime import datetime

from bs4 import BeautifulSoup
from sqlalchemy import func, select, update

from .business_monitor_access import collection_actor
from .config import DomainError
from .monitoring_subjects import _savepoint
from .simap_sources import aware, parse_publication
from .simap_tender_facts import facts_from_publication
from .tender_contracts import TenderProfile, match_lot
from .tender_evidence import store_material, store_snapshot
from .tender_models import TenderDossier, TenderDossierVersion, TenderMonitor
from .tender_rights import require_permitted
from .tender_storage import StorageLimits, check_version_capacity


def normalized(value):
    """Remove HTML presentation noise, preserving all original evidence separately."""
    if isinstance(value, str):
        soup = BeautifulSoup(value, "html.parser")
        for node in soup(["script", "style", "template"]):
            node.decompose()
        return " ".join(soup.get_text(" ", strip=True).split())
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        result = [normalized(item) for item in value]
        # Source criterion identity, not list order, identifies a requirement.
        if result and all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in result):
            if len({item["id"] for item in result}) != len(result):
                raise ValueError("Ambiguous source criterion identity")
            result.sort(key=lambda item: item["id"])
        return result
    return value


def public_material(record, facts, shared=None):
    raw = record["original"]
    if facts.lot_id:
        if raw.get("lot"):
            block = raw["lot"]
        else:
            block = next(lot for lot in raw["lots"] if lot["id"] == facts.lot_id)
        prefix = "/lot" if raw.get("lot") else f"/lots/{raw['lots'].index(block)}"
    else:
        block, prefix = raw.get("procurement") or {}, "/procurement"

    def section(value, locator):
        common = locator in {
            "/type",
            "/dates/offerDeadline",
            "/criteria",
            "/terms",
            "/dates/qnas",
            "/project-info/offerLanguages",
        }
        if common and shared is not None and locator in shared:
            return shared[locator]
        result = {
            "value": normalized(value),
            "locator": locator,
            "coverage": "known" if value is not None else "unknown",
        }
        if common and shared is not None:
            shared[locator] = result
        return result

    criteria = {
        key: block[key]
        for key in (
            "qualificationCriteria",
            "qualificationCriteriaInDocuments",
            "qualificationCriteriaAsPDF",
            "qualificationCriteriaNote",
            "awardCriteriaSelection",
            "awardCriteria",
            "awardCriteriaNote",
            "weightedQualificationCriteria",
            "weightedQualificationCriteriaInDocuments",
            "weightedQualificationCriteriaNote",
        )
        if key in block
    }
    procurement = {
        key: value
        for key, value in block.items()
        if key
        not in {
            "id",
            "lotNumber",
            "title",
            *criteria,
        }
    }
    return {
        "phase": section(facts.phase, "/type"),
        "title": section(
            block.get("title") if facts.lot_id else (raw.get("project-info") or {}).get("title"),
            prefix + "/title" if facts.lot_id else "/project-info/title",
        ),
        "deadline": section(
            {"utc": record["offer_deadline"]["utc"], "status": record["offer_deadline"]["status"]},
            "/dates/offerDeadline",
        ),
        "procurement": section(procurement or None, prefix),
        "lot_criteria": section(criteria or None, prefix),
        "project_criteria": section(raw.get("criteria"), "/criteria"),
        "terms": section(raw.get("terms"), "/terms"),
        # This is only the published Q&A schedule, never a claim to have answers.
        "qa_schedule": section((raw.get("dates") or {}).get("qnas"), "/dates/qnas"),
        "offer_languages": section(
            sorted(facts.offer_languages) if facts.offer_languages else None, "/project-info/offerLanguages"
        ),
    }


def material_changes(previous, current):
    result = []
    for field, after in current.items():
        before = previous.get(field)
        if before is None or (before["coverage"], before["value"]) == (after["coverage"], after["value"]):
            continue
        known = before["coverage"] == after["coverage"] == "known"
        if field == "deadline":
            known = known and before["value"]["status"] == after["value"]["status"] == "known"
        result.append(
            {
                "field": field,
                "kind": "field_changed" if known else "coverage_changed",
                "before_locator": before["locator"],
                "after_locator": after["locator"],
            }
        )
    return result


def card_summary(material):
    """Bounded display projection; the detail reader retains exact originals."""
    title = material["title"]["value"] or {}
    return {
        "title": {
            language: text[:500]
            for language, text in title.items()
            if language in {"de", "en", "fr", "it"} and isinstance(text, str)
        },
        "title_truncated": any(isinstance(text, str) and len(text) > 500 for text in title.values()),
        "phase": material["phase"]["value"],
        "deadline": material["deadline"]["value"],
    }


def publication_ordinal(record):
    base = record["original"]["base"]
    number = base.get("publicationNumber")
    if not isinstance(number, str) or not (match := re.fullmatch(r"([0-9]{1,15})-([0-9]{1,8})", number)):
        raise ValueError("A source publication sequence is required before advancing a dossier")
    if base.get("projectNumber") is not None and str(base["projectNumber"]) != match[1]:
        raise ValueError("Publication number conflicts with its project number")
    ordinal = int(match[2])
    if ordinal < 1:
        raise ValueError("Invalid publication sequence")
    return ordinal


def observe_publication(
    session,
    monitor_id,
    record,
    *,
    now,
    cpv_ancestry=(),
    authority_levels=None,
    discover=True,
    allowed_lot_ids=None,
    storage_limits=StorageLimits(),
):
    """Consume a permitted public record fetched by a trusted source worker.

    This function is not exposed as an HTTP endpoint. The eventual worker must
    enforce current source policy and acquisition leases before calling it.
    One transaction includes every affected lot; caller rollback undoes all.
    """
    now = aware(now)
    monitor = session.scalar(
        select(TenderMonitor)
        .where(
            TenderMonitor.id == monitor_id,
            TenderMonitor.organization_id == session.info.get("organization_id"),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if monitor is None or monitor.status != "active":
        return []
    collection_actor(session, monitor)
    require_permitted(session, record["project_id"], record["publication_id"])
    checked = parse_publication(
        record["original"], project_id=record["project_id"], publication_id=record["publication_id"], now=now
    )
    if checked["evidence_sha256"] != record["evidence_sha256"]:
        raise ValueError("Publication evidence does not match its fingerprint")
    ordinal = publication_ordinal(checked)
    profile = TenderProfile.model_validate(monitor.configuration)
    lots = facts_from_publication(
        checked, now=now, cpv_ancestry=cpv_ancestry, authority_levels=authority_levels
    )
    touched = []
    snapshot_id = None
    shared_material, stored_sections = {}, {}
    with _savepoint(session):
        for facts in lots:
            if allowed_lot_ids is not None and (facts.lot_id or "") not in allowed_lot_ids:
                continue
            row = session.scalar(
                select(TenderDossier)
                .where(
                    TenderDossier.monitor_id == monitor_id,
                    TenderDossier.organization_id == monitor.organization_id,
                    TenderDossier.project_id == facts.project_id,
                    TenderDossier.lot_key == (facts.lot_id or ""),
                )
                .execution_options(populate_existing=True)
            )
            assessment = match_lot(profile, facts, now=now)
            if row is None:
                if not discover or assessment["verdict"] not in {"match", "needs_review"}:
                    continue
                row = TenderDossier(
                    organization_id=monitor.organization_id,
                    monitor_id=monitor_id,
                    project_id=facts.project_id,
                    lot_key=facts.lot_id or "",
                    version=1,
                    latest_sequence=0,
                    latest_ordinal=0,
                    review_state="new",
                    following=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
            # Existing dossiers retain updates even if their new phase/profile
            # no longer qualifies as a newly discoverable opportunity.
            duplicate = session.scalar(
                select(TenderDossierVersion.id).where(
                    TenderDossierVersion.dossier_id == row.id,
                    TenderDossierVersion.organization_id == row.organization_id,
                    TenderDossierVersion.publication_id == facts.publication_id,
                    TenderDossierVersion.source_hash == facts.evidence_sha256,
                    TenderDossierVersion.profile_revision == monitor.revision,
                )
            )
            if duplicate:
                continue
            check_version_capacity(session, monitor, storage_limits)
            previous = session.scalar(
                select(TenderDossierVersion).where(
                    TenderDossierVersion.dossier_id == row.id,
                    TenderDossierVersion.organization_id == row.organization_id,
                    TenderDossierVersion.sequence == row.latest_sequence,
                )
            )
            if (
                previous
                and previous.publication_ordinal == ordinal
                and previous.publication_id != facts.publication_id
            ):
                raise ValueError("Conflicting source publications have the same sequence")
            if previous is not None:
                # A permitted new publication does not authorize reuse of a
                # withdrawn old original for derived comparisons.
                require_permitted(session, facts.project_id, previous.publication_id)
            material = public_material(checked, facts, shared_material)
            changes = material_changes(previous.material, material) if previous else []
            profile_changed = previous is not None and previous.profile_revision != monitor.revision
            late = ordinal < row.latest_ordinal
            kind = (
                "late_evidence"
                if late
                else "new_opportunity"
                if previous is None
                else "material_update"
                if changes
                else "profile_reassessment"
                if profile_changed
                else "source_update"
            )
            sequence = (
                session.scalar(
                    select(func.max(TenderDossierVersion.sequence)).where(
                        TenderDossierVersion.dossier_id == row.id,
                        TenderDossierVersion.organization_id == row.organization_id,
                    )
                )
                or 0
            ) + 1
            if snapshot_id is None:
                snapshot_id = store_snapshot(session, checked, now, limits=storage_limits)
            version = TenderDossierVersion(
                organization_id=row.organization_id,
                dossier_id=row.id,
                sequence=sequence,
                publication_id=facts.publication_id,
                publication_ordinal=ordinal,
                profile_revision=monitor.revision,
                document_observation_id=previous.document_observation_id if previous else None,
                source_hash=snapshot_id,
                publish_after=datetime.fromisoformat(checked["publish_after"]),
                material_keys=sorted(material),
                summary={
                    **card_summary(material),
                    "verdict": assessment["verdict"],
                    "match_scope": "lot"
                    if assessment["matches"]
                    else "project_context"
                    if assessment["project_context"]
                    else "none",
                },
                match=assessment,
                changes=[] if late else changes,
                kind=kind,
                observed_at=now,
            )
            session.add(version)
            session.flush()
            store_material(session, version, material, now, cache=stored_sections, limits=storage_limits)
            values = {"version": row.version + 1}
            if not late:
                values.update(latest_sequence=sequence, latest_ordinal=ordinal, updated_at=now)
                if (changes or profile_changed) and row.review_state == "reviewed":
                    values["review_state"] = "needs_review"
            changed = session.execute(
                update(TenderDossier)
                .where(
                    TenderDossier.id == row.id,
                    TenderDossier.organization_id == row.organization_id,
                    TenderDossier.version == row.version,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                raise DomainError(
                    "Tender evidence changed concurrently. Retry this observation.",
                    409,
                    "tender_version_conflict",
                )
            session.flush()
            touched.append(row.id)
            from .tender_delivery import record_intent

            record_intent(session, monitor, row, version, now)
    return touched
