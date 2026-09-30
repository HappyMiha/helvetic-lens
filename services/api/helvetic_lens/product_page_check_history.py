"""Read native page-check history through current dossier and corpus authority."""
from datetime import UTC, datetime

from sqlalchemy import func, select

from .corpus_access import visible
from .db import utcnow
from .models import Comparison, DocumentWatch, Scan, ScanItem, Version
from .product_api import fail, iso
from .product_investigation_models import Investigation, MonitoringResearchTrigger
from .product_monitoring_outcomes import findings
from .product_page_research import readable
from .product_public_research import sources_visible
from .product_source_reviews import current_reviews

CONTRACT = "page-check-history/v1"
LIMIT = 10
OUTCOMES = {"baseline_created", "changed", "unchanged", "skipped", "failed", "cancelled"}
ANALYSIS = {"pending", "queued", "running", "succeeded", "complete", "completed", "failed", "not_needed", "not_configured", "not_run", "unsupported"}


def event_time(events, stage, created_at):
    for event in reversed(events or []):
        if not isinstance(event, dict) or event.get("stage") != stage:
            continue
        try:
            value = datetime.fromisoformat(event["at"])
            if value.tzinfo is not None and value >= created_at.replace(tzinfo=UTC):
                return value.astimezone(UTC).isoformat()
        except (KeyError, TypeError, ValueError):
            pass
    return None


def version(session, parent, law_id, identifier, blocked):
    if not identifier:
        return None
    value = session.execute(select(Version.id, Version.title, Version.evidence_revision,
        Version.content_hash, Version.created_at, Version.source_url, Version.synthetic, Version.origin)
        .where(Version.id == identifier, Version.law_id == law_id, visible(Version, parent.organization_id))).mappings().first()
    if not value or value["source_url"] in blocked:
        return None
    return {**dict(value), "created_at": iso(value["created_at"])}


def research_result(session, parent, watch_id, captured, item):
    if not captured or datetime.fromisoformat(captured["created_at"]) < item["created_at"].replace(tzinfo=UTC):
        return None  # Unchanged checks do not inherit research for an older capture.
    trigger = session.scalar(select(MonitoringResearchTrigger).where(
        MonitoringResearchTrigger.dossier_id == parent.id,
        MonitoringResearchTrigger.source_kind == "watched_page",
        MonitoringResearchTrigger.source_identifier == watch_id + ":" + captured["id"],
        MonitoringResearchTrigger.source_revision == str(captured["evidence_revision"]))
        .order_by(MonitoringResearchTrigger.created_at.desc(), MonitoringResearchTrigger.id.desc()).limit(1))
    if not trigger:
        return None
    if not readable(session, parent, trigger.source_json):
        return {"state": "unavailable", "investigation_id": None, "finding": None}
    page = trigger.source_json.get("page", {})
    previous = page.get("previous", {})
    if page.get("revision") != captured["evidence_revision"] or not session.scalar(select(Version.id).where(
            Version.id == previous.get("version_id"), Version.evidence_revision == previous.get("revision"),
            Version.law_id == item["law_id"], visible(Version, parent.organization_id))):
        return {"state": "unavailable", "investigation_id": None, "finding": None}
    run = session.scalar(select(Investigation).where(Investigation.id == trigger.investigation_id,
        Investigation.dossier_id == parent.id, Investigation.publication_id.is_(None), sources_visible())) if trigger.investigation_id else None
    if not run:
        return {"state": trigger.state if not trigger.investigation_id else "unavailable", "investigation_id": None, "finding": None}
    evidence = findings(session, run) if run.status in {"completed", "failed"} else []
    return {"state": run.status, "investigation_id": run.id, "finding": evidence[0] if evidence else None}


def check_payload(session, parent, watch_id, item, blocked):
    stage = item["stage"]
    result = {"id": item["id"], "created_at": iso(item["created_at"]),
        "started_at": event_time(item["events"], "fetching", item["created_at"]),
        "finished_at": event_time(item["events"], stage, item["created_at"]) if stage in {"complete", "failed"} else None,
        "outcome": "pending", "analysis_status": item["analysis_status"] if item["analysis_status"] in ANALYSIS else "unknown",
        "versions": [], "research": None, "limitation": None}
    if stage in {"interrupted", "cancelled"} or item["result"] == "cancelled":
        result["outcome"] = "interrupted"
    elif stage == "failed" or item["result"] == "failed":
        result["outcome"] = "failed"
        result["limitation"] = "This check could not be completed. The earlier saved evidence is retained; no new successful source check is established."
    elif stage == "complete":
        result["outcome"] = item["live_result"] if item["live_result"] in OUTCOMES else item["result"] if item["result"] in OUTCOMES else "unknown"
    else:
        return result
    if item["live_result"] in {"identity_unknown", "identity_mismatch"}:
        result["outcome"] = "identity_unresolved"
        result["limitation"] = "A document was captured, but its identity was not accepted. It was not made the current source version."
    if not item["new_version_id"]:
        return result
    current = version(session, parent, item["law_id"], item["new_version_id"], blocked)
    comparison_id = item["comparison_id"] if item["mode"] == "historical" else item["monitoring_comparison_id"] or item["comparison_id"]
    comparison = session.execute(select(Comparison.old_version_id, Comparison.new_version_id).where(
        Comparison.id == comparison_id, Comparison.law_id == item["law_id"],
        visible(Comparison, parent.organization_id))).mappings().first() if comparison_id else None
    prior_id = comparison["old_version_id"] if comparison else item["baseline_version_id"]
    previous = version(session, parent, item["law_id"], prior_id, blocked) if prior_id else None
    if (not current or (prior_id and not previous) or (comparison_id and not comparison)
            or (comparison and comparison["new_version_id"] != current["id"])):
        result.update(outcome="evidence_unavailable", analysis_status="unavailable",
            limitation="The supporting saved versions are no longer available in this dossier.")
        return result
    result["versions"] = ([{**previous, "label": "Earlier version"}] if previous and previous["id"] != current["id"] else []) + [
        {**current, "label": "Captured version"}]
    if current["synthetic"] or current["origin"] != "live" or (previous and (previous["synthetic"] or previous["origin"] != "live")):
        result.update(outcome="example_or_import", limitation="Example or imported evidence does not establish a successful live-source check.")
    elif stage == "complete" and item["mode"] == "historical":
        result["outcome"] = "historical_comparison"
    if result["outcome"] in {"changed", "baseline_created", "historical_comparison"}:
        result["research"] = research_result(session, parent, watch_id, current, item)
    return result


def history(session, parent, document, *, offset=0, as_of=None):
    if parent.monitoring_audience == "team":
        fail("Workspace page history is unavailable in members-only dossiers.", 404)
    blocked = {url for url, review in current_reviews(session, parent.id).items() if review.data_json["decision"] == "exclude"}
    if document["url"] in blocked:
        fail("This source is no longer available in this dossier.", 404)
    watch_id = session.scalar(select(DocumentWatch.id).where(DocumentWatch.law_id == document["id"],
        DocumentWatch.organization_id == parent.organization_id))
    now = utcnow()
    if (offset and as_of is None) or (as_of is not None and (as_of.tzinfo is None or as_of > now)):
        fail("Open the first page to restart source-check history.", 422)
    captured = as_of or now
    query = select(ScanItem).join(Scan, Scan.id == ScanItem.scan_id).where(
        ScanItem.organization_id == parent.organization_id, Scan.organization_id == parent.organization_id,
        ScanItem.law_id == document["id"], ScanItem.created_at <= captured)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    # Scalar metadata only: neither version bodies nor comparison diffs are loaded.
    items = session.execute(query.with_only_columns(*[getattr(ScanItem, key) for key in (
        "id", "law_id", "created_at", "events", "stage", "result", "live_result", "analysis_status", "mode",
        "baseline_version_id", "new_version_id", "comparison_id", "monitoring_comparison_id")])
        .order_by(ScanItem.created_at.desc(), ScanItem.id.desc()).offset(offset).limit(LIMIT)).mappings()
    return {"schema_id": CONTRACT, "dossier_id": parent.id, "document": document,
        "items": [check_payload(session, parent, watch_id, item, blocked) for item in items],
        "total": total, "offset": offset, "page_size": LIMIT, "as_of": iso(captured),
        "next_offset": offset + LIMIT if offset + LIMIT < total else None,
        "scope": "Retained workspace checks for this connected page, not a dossier-wide scan. "
            "Newer checks appear after refresh; later retries or corrections can update saved records. "
            "Connecting a page can save its first version without a separate check-history record.",
        "ai_calls": 0}
