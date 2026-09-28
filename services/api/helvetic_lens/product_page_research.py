"""Research observes retained live page versions; it never acquires web content."""
import hashlib

from sqlalchemy import String, and_, cast, exists, func, or_, select
from sqlalchemy.orm import aliased

from .config import DomainError
from .corpus_access import visible
from .models import DocumentWatch, Law, Version
from .product_api import fail, iso
from .product_investigation_models import MonitoringResearchTrigger as Trigger
from .product_models import DossierEntry
from .product_source_reviews import current_reviews

MAX_TEXT = 200000
EXCERPT = 12000


def linked(parent_id, law_id):
    return exists(select(DossierEntry.id).where(DossierEntry.dossier_id == parent_id,
        DossierEntry.kind == "monitor", DossierEntry.data_json["law_id"].as_string() == law_id))


def watches(parent):
    return select(DocumentWatch).join(Law, Law.id == DocumentWatch.law_id).where(
        DocumentWatch.organization_id == parent.organization_id, visible(Law, parent.organization_id),
        Law.active.is_(True), linked(parent.id, Law.id))


def retained_visible(dossier_id, organization_id, document_id, version_id):
    """Reading a retained excerpt needs its current corpus and dossier link.

    Pausing acquisition does not erase historical evidence or hide it from its
    authorized readers. Corpus withdrawal and unlinking do revoke this access.
    """
    version, law, watch = aliased(Version), aliased(Law), aliased(DocumentWatch)
    return exists(select(version.id).join(law, law.id == version.law_id).join(watch, watch.law_id == law.id)
        .where(version.id == version_id, law.id == document_id, visible(version, organization_id),
            visible(law, organization_id), version.synthetic.is_(False), version.origin == "live",
            watch.organization_id == organization_id, linked(dossier_id, law.id)))


def readable(session, parent, source):
    page = source.get("page")
    if not page:
        return True
    if parent.monitoring_audience == "team":
        return False
    ids = (page["version_id"], page["previous"]["version_id"])
    urls = {source.get("url"), page["previous"].get("source_url"), session.scalar(select(Law.url).where(Law.id == page["document_id"])),
        *session.scalars(select(Version.source_url).where(Version.id.in_(ids)))}
    excluded = any(review.data_json["decision"] == "exclude"
        for url, review in current_reviews(session, parent.id).items() if url in urls)
    return not excluded and all(session.scalar(select(retained_visible(
        parent.id, parent.organization_id, page["document_id"], version_id)))
        for version_id in ids)


def results_visible(run):
    """SQL counterpart of readable(), before derived counts and pagination.

    The retained snapshot alone has only the new version. Its paired previous
    version and canonical/current source URLs are pinned in the trigger receipt.
    """
    from .product_models import ProductDossier

    trigger, parent = aliased(Trigger), aliased(ProductDossier)
    review, newer = aliased(DossierEntry), aliased(DossierEntry)
    page = trigger.source_json["page"]
    ids = (page["version_id"].as_string(), page["previous"]["version_id"].as_string())
    has_newer = exists(select(newer.id).where(newer.dossier_id == review.dossier_id,
        newer.kind == "source_review", newer.url == review.url,
        (newer.data_json["revision"].as_integer() > review.data_json["revision"].as_integer()) |
        ((newer.data_json["revision"].as_integer() == review.data_json["revision"].as_integer()) & (newer.id > review.id))))
    excluded = exists(select(review.id).where(review.dossier_id == trigger.dossier_id,
        review.kind == "source_review", review.data_json["decision"].as_string() == "exclude", ~has_newer,
        or_(review.url == trigger.source_json["url"].as_string(),
            review.url == page["previous"]["source_url"].as_string(),
            review.url.in_(select(Law.url).where(Law.id == page["document_id"].as_string())),
            review.url.in_(select(Version.source_url).where(Version.id.in_(ids))))))
    unavailable = exists(select(trigger.id).join(parent, parent.id == trigger.dossier_id)
        .where(trigger.investigation_id == run.id, trigger.source_kind == "watched_page",
            or_(parent.monitoring_audience == "team", excluded,
                *(~retained_visible(trigger.dossier_id, trigger.organization_id,
                    page["document_id"].as_string(), identifier) for identifier in ids))))
    return ~unavailable


def readiness(session, parent):
    allowed = parent.monitoring_audience != "team"
    query = watches(parent)
    total = session.scalar(select(func.count()).select_from(query.subquery())) if allowed else 0
    active = session.scalar(select(func.count()).select_from(query.where(DocumentWatch.active.is_(True),
        DocumentWatch.auto_check_enabled.is_(True)).subquery())) if allowed else 0
    reason = ("Workspace page watches are unavailable in members-only dossiers." if not allowed else
        "Connect a source page in this dossier to monitor its future saved changes." if not total else
        "Enable a linked page's daily checks before it can trigger research." if not active else
        "Future saved changes from active daily page watches can be researched. Source access and exclusions are rechecked for each change.")
    return {"allowed": allowed, "linked": total, "active": active, "reason": reason}


def versions(parent, document_id):
    return select(Version.id, Version.evidence_revision, Version.content_hash, Version.title,
        Version.source_url, Version.created_at, func.substr(Version.text, 1, MAX_TEXT + 1).label("text"))\
        .join(Law, Law.id == Version.law_id).where(Version.law_id == document_id,
            visible(Law, parent.organization_id), visible(Version, parent.organization_id),
            Version.synthetic.is_(False), Version.origin == "live")


def capture(session, parent, identifier, revision, *, retained=None):
    if parent.monitoring_audience == "team":
        fail("Workspace page research is unavailable in a members-only dossier.", 409)
    watch_id, separator, version_id = identifier.partition(":")
    watch = session.scalar(watches(parent).where(DocumentWatch.id == watch_id,
        DocumentWatch.active.is_(True), DocumentWatch.auto_check_enabled.is_(True)))
    if not separator or not watch:
        fail("This page watch is no longer active and linked to the dossier.", 409)
    current = session.execute(versions(parent, watch.law_id).where(Version.id == version_id)).mappings().first()
    if not current or str(current["evidence_revision"]) != revision:
        fail("The saved page is unavailable or its captured revision changed.", 409)
    query = versions(parent, watch.law_id)
    if retained:
        previous = session.execute(query.where(Version.id == retained["previous"]["version_id"])).mappings().first()
        if not previous or previous["evidence_revision"] != retained["previous"]["revision"]:
            fail("The earlier saved page is unavailable or its captured revision changed.", 409)
    else:
        previous = session.execute(query.where(or_(Version.created_at < current["created_at"],
            and_(Version.created_at == current["created_at"], Version.id < current["id"])))
            .order_by(Version.created_at.desc(), Version.id.desc()).limit(1)).mappings().first()
    if not previous:
        fail("This is a saved baseline. A later retained page version is needed to compare changes.", 409)
    law = session.get(Law, watch.law_id)
    urls = {law.url, current["source_url"], previous["source_url"]}
    if any(review.data_json["decision"] == "exclude" for url, review in current_reviews(session, parent.id).items() if url in urls):
        fail("This source is excluded from dossier research.", 409)
    before, after = previous["text"], current["text"]
    if len(before) > MAX_TEXT or len(after) > MAX_TEXT:
        fail("This page exceeds the 200,000-character automatic comparison limit. Inspect its saved versions.", 409)
    if not after.strip():
        fail("The new saved page has no readable text to research.", 409)
    if before == after:
        fail("The retained versions contain the same text; no new textual evidence was found.", 409)
    first = next((i for i, (a, b) in enumerate(zip(before, after)) if a != b), min(len(before), len(after)))
    start = max(0, first - 180)
    # A single contiguous window preserves literal quotations. Previous text is
    # retained for inspection only and never enters new-source extraction.
    text = after[start:start + EXCERPT]
    page = {"watch_id": watch.id, "document_id": watch.law_id,
        "version_id": current["id"], "revision": current["evidence_revision"], "content_hash": current["content_hash"],
        "previous": {"version_id": previous["id"], "revision": previous["evidence_revision"],
            "content_hash": previous["content_hash"], "captured_at": iso(previous["created_at"]),
            "source_url": previous["source_url"] or law.url},
        "first_difference": first, "excerpt_start": start, "before": before[start:start + EXCERPT],
        "after": text, "before_characters": len(before), "after_characters": len(after),
        "partial": start > 0 or max(len(before), len(after)) > start + EXCERPT}
    return {"key": identifier + ":" + revision, "kind": "saved_page_extract", "title": current["title"] or watch.display_name,
        "url": current["source_url"] or law.url, "text": text, "date": iso(current["created_at"]),
        "sha256": hashlib.sha256(text.encode()).hexdigest(), "page": page}


def collect(session, parent, policy):
    identity = DocumentWatch.id + ":" + Version.id
    recorded = exists(select(Trigger.id).where(Trigger.dossier_id == parent.id,
        Trigger.source_kind == "watched_page", Trigger.source_identifier == identity,
        Trigger.source_revision == cast(Version.evidence_revision, String)))
    # A page linked after capture does not retroactively authorize its body.
    connected_before = exists(select(DossierEntry.id).where(DossierEntry.dossier_id == parent.id,
        DossierEntry.kind == "monitor", DossierEntry.data_json["law_id"].as_string() == Version.law_id,
        DossierEntry.created_at < Version.created_at))
    candidates = session.execute(select(DocumentWatch.id, Version.id, Version.evidence_revision, Version.created_at)
        .select_from(DocumentWatch).join(Version, Version.law_id == DocumentWatch.law_id).join(Law, Law.id == Version.law_id)
        .where(DocumentWatch.organization_id == parent.organization_id, DocumentWatch.active.is_(True),
            DocumentWatch.auto_check_enabled.is_(True), Law.active.is_(True), connected_before,
            visible(Law, parent.organization_id), visible(Version, parent.organization_id),
            Version.origin == "live", Version.synthetic.is_(False), Version.created_at > policy.starts_on,
            Version.created_at > DocumentWatch.created_at, ~recorded)
        .order_by(Version.created_at, Version.id, DocumentWatch.id).limit(100)).all()
    for watch_id, version_id, revision, created_at in candidates:
        trigger = Trigger(dossier_id=parent.id, organization_id=parent.organization_id, policy_id=policy.id,
            policy_revision=policy.revision, source_kind="watched_page", source_identifier=watch_id + ":" + version_id,
            source_revision=str(revision), matched_at=created_at)
        session.add(trigger)
        try:
            trigger.source_json = capture(session, parent, trigger.source_identifier, trigger.source_revision)
        except DomainError as exc:
            trigger.state, trigger.reason = "skipped", exc.message


def page_payload(source):
    page = source.get("page")
    return {**page, "before": page["before"][:1500], "after": page["after"][:1500],
        "preview_partial": len(page["before"]) > 1500 or len(page["after"]) > 1500} if page else None
