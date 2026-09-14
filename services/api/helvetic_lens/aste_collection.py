"""One leased public GET at a time, committed checkpoints and atomic journal admission."""

import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import String, case, cast, delete, func, select

from . import aste_parser as parser
from . import auction_sources as sources
from .aste_models import AsteCollector, AsteItem, AsteListingEvidence
from .auction_contracts import AuctionFacts, Document, Documents, fingerprint
from .config import DomainError

MAX_ITEMS = 5000
MAX_PAGES = 1000
MAX_PROOFS = 10000
MAX_BYTES = 128 * 1024 * 1024
LEASE_SECONDS = 120


def _fail(code):
    raise DomainError("The official auction collection is unavailable.", 409, code)


def scope(session, permission_id, *, now):
    _, policy = sources.require_permission(session, permission_id, now=now, purpose="acquisition")
    sources.require_permission(session, permission_id, now=now)
    if policy.source_key != parser.SOURCE_KEY or policy.endpoint != parser.ORIGIN + "/" or policy.native_access is None:
        _fail("aste_native_access_required")
    selected = sources._selection(session, policy.source_key)
    if selected is None or selected.permission_id != permission_id:
        _fail("aste_source_selection_conflict")
    return policy, selected


def _reset(item):
    item.stage, item.detail_payload, item.detail_at, item.payload_expires_at = "detail", None, None, None
    item.documents, item.document_index = [], 0


def _collector(session):
    return session.scalar(select(AsteCollector).where(AsteCollector.source_key == parser.SOURCE_KEY)
        .with_for_update().execution_options(populate_existing=True))


def _storage(session, incoming):
    sizes = [session.scalar(select(func.coalesce(func.sum(func.length(column)), 0))) for column in
             (AsteItem.detail_payload, AsteListingEvidence.raw_payload)]
    if sum(sizes) + incoming > MAX_BYTES:
        _fail("aste_capacity_reached")


def claim(session, permission_id, *, now):
    now = sources._clock(now)
    policy, selected = scope(session, permission_id, now=now)
    state = _collector(session)
    if state is None:
        state = AsteCollector(source_key=parser.SOURCE_KEY, permission_id=permission_id,
            generation=selected.generation, discovery_due_at=now, next_request_at=now)
        session.add(state)
        session.flush()
    # Account-wide backoff survives permission replacement.
    if state.lease_until and sources._utc(state.lease_until) > now or sources._utc(state.next_request_at) > now:
        return None
    if state.permission_id != permission_id or state.generation != selected.generation:
        # Retain known public identities for revisits; never reuse licensed payloads
        # or category conclusions across a replaced source permission.
        for item in session.scalars(select(AsteItem)):
            item.permission_id, item.generation, item.next_check_at = permission_id, selected.generation, now
            item.category_proofs, item.last_error = {}, None
            item.last_record_at = None
            _reset(item)
        state.permission_id, state.generation = permission_id, selected.generation
        state.listing_queue, state.visited, state.category_labels = [], [], {}
        state.discovery_due_at, state.last_error = now, None
        state.last_record_at, state.last_completed_at = None, None
    if not state.listing_queue and sources._utc(state.discovery_due_at) <= now:
        state.listing_queue = [parser.listing_url(), parser.listing_url(upcoming=True)]
        state.visited, state.category_labels = [], {}
        state.discovery_due_at = now + timedelta(seconds=policy.min_poll_seconds)
    item = session.scalar(select(AsteItem).where(AsteItem.permission_id == permission_id,
        AsteItem.generation == selected.generation, AsteItem.next_check_at <= now)
        .order_by(case((AsteItem.stage != "detail", 0), else_=1), AsteItem.next_check_at, AsteItem.identifier).limit(1))
    if state.listing_queue and (state.prefer_listing or item is None):
        job = {"kind": "listing", "url": state.listing_queue[0]}
        state.prefer_listing = False
    elif item is not None:
        if ((item.payload_expires_at and sources._utc(item.payload_expires_at) <= now)
                or (item.detail_at and now - sources._utc(item.detail_at) > timedelta(seconds=policy.max_age_seconds))):
            _reset(item)
            item.last_error = "aste_detail_stale"
            item.next_check_at = now + timedelta(seconds=policy.min_poll_seconds)
            session.flush()
            return None
        if item.stage == "detail":
            url = parser.detail_url(item.identifier)
        elif item.stage == "documents":
            if not 0 <= item.document_index < len(item.documents):
                _fail("aste_checkpoint_invalid")
            url = item.documents[item.document_index]["url"]
        elif item.stage in ("status", "admit"):
            url = parser.status_url(item.identifier)
        else:
            _fail("aste_checkpoint_invalid")
        job = {"kind": item.stage, "identifier": item.identifier, "url": url, "document_index": item.document_index}
        state.prefer_listing = True
    else:
        return None
    token = str(uuid4())
    state.lease_token, state.lease_until, state.lease_job = token, now + timedelta(seconds=LEASE_SECONDS), job
    state.last_request_at = now
    state.next_request_at = now + timedelta(seconds=policy.native_access.request_interval_seconds)
    session.flush()
    return {"token": token, "permission_id": permission_id, "generation": selected.generation, **job}


def guard(session, ticket, *, now):
    policy, selected = scope(session, ticket["permission_id"], now=now)
    state = _collector(session)
    job = {k: v for k, v in ticket.items() if k not in ("token", "permission_id", "generation")}
    if (state is None or state.permission_id != ticket["permission_id"] or state.generation != ticket["generation"]
            or selected.generation != ticket["generation"] or state.lease_token is None
            or not hmac.compare_digest(state.lease_token, ticket["token"])
            or state.lease_until is None or not now < sources._utc(state.lease_until) or state.lease_job != job):
        _fail("aste_lease_lost")
    return policy, selected, state


def _listing(session, policy, selected, state, ticket, raw, now):
    if not state.listing_queue or state.listing_queue[0] != ticket["url"]:
        _fail("aste_checkpoint_invalid")
    result = parser.parse_listing(raw, url=ticket["url"])
    parts = parser._listing_parts(ticket["url"])
    pending = list(state.listing_queue[1:])
    visited = [*state.visited, ticket["url"]]
    labels = dict(state.category_labels)
    if result.next_url:
        if result.next_url in visited or result.next_url in pending:
            _fail("aste_listing_inconsistent")
        pending.append(result.next_url)
    if parts["category"] is None and parts["page"] == 1:
        for category_id, label in result.categories:
            labels[category_id] = label
            url = parser.listing_url(upcoming=parts["upcoming"], category=category_id)
            if url not in visited and url not in pending:
                pending.append(url)
    if len(visited) + len(pending) > MAX_PAGES:
        _fail("aste_capacity_reached")
    _storage(session, len(raw))
    if session.scalar(select(func.count()).select_from(AsteListingEvidence)) >= MAX_PROOFS:
        _fail("aste_capacity_reached")
    label = dict(result.categories).get(parts["category"])
    metadata = {"url": ticket["url"], "observed_at": now.isoformat(),
        "category_id": parts["category"], "category_label": label, "identifiers": list(result.identifiers)}
    policy_id = state.permission_id
    evidence = AsteListingEvidence(permission_id=policy_id, url=ticket["url"],
        raw_payload=raw, raw_hash=result.sha256, metadata_hash=fingerprint(metadata), observed_at=now,
        raw_expires_at=now + timedelta(seconds=policy.raw_retention_seconds),
        normalized_expires_at=now + timedelta(seconds=policy.normalized_retention_seconds),
        category_id=parts["category"], category_label=label, identifiers=list(result.identifiers))
    session.add(evidence)
    session.flush()
    for identifier in result.identifiers:
        item = session.get(AsteItem, identifier)
        if item is None:
            if session.scalar(select(func.count()).select_from(AsteItem)) >= MAX_ITEMS:
                _fail("aste_capacity_reached")
            item = AsteItem(identifier=identifier, permission_id=policy_id, generation=selected.generation,
                next_check_at=now, last_seen_at=now, category_proofs={})
            session.add(item)
            session.flush()
        item.last_seen_at = now
        if parts["category"]:
            item.category_proofs = {**item.category_proofs, parts["category"]: evidence.id}
    state.listing_queue, state.visited, state.category_labels = pending, visited, labels
    if not pending:
        state.last_completed_at, state.last_error = now, None
        state.discovery_due_at = now + timedelta(seconds=policy.min_poll_seconds)


def _category(session, policy, item, now):
    mapped, evidence = set(), []
    for category_id, proof_id in item.category_proofs.items():
        proof = session.get(AsteListingEvidence, proof_id)
        if (proof is None or proof.permission_id != item.permission_id
                or sources._utc(proof.normalized_expires_at) <= now or proof.identifiers is None
                or not timedelta(0) <= now - sources._utc(proof.observed_at) <= timedelta(seconds=policy.max_age_seconds)
                or item.identifier not in proof.identifiers or proof.category_id != category_id):
            continue
        metadata = {"url": proof.url, "observed_at": sources._utc(proof.observed_at).isoformat(),
            "category_id": proof.category_id, "category_label": proof.category_label, "identifiers": proof.identifiers}
        if (fingerprint(metadata) != proof.metadata_hash or proof.raw_payload is not None
                and hashlib.sha256(proof.raw_payload).hexdigest() != proof.raw_hash):
            continue
        choice = policy.native_access.category_mapping.get(category_id)
        if choice is None or choice.label != proof.category_label:
            continue
        mapped.add(choice.category)
        evidence.append({"id": proof.id, "url": proof.url, "source_sha256": proof.raw_hash,
            "category_id": category_id, "label": proof.category_label, "observed_at": sources._utc(proof.observed_at).isoformat()})
    # A publisher item spanning conflicting configured categories remains unknown.
    return (next(iter(mapped)) if len(mapped) == 1 else None), evidence


def _admit(session, policy, selected, state, item, result, now):
    if item.detail_at is None or now - sources._utc(item.detail_at) > timedelta(seconds=policy.max_age_seconds):
        _fail("aste_detail_stale")
    references = [(d.official_id, d.url, d.title) for d in result.documents]
    retained = [(d["official_id"], d["url"], d["title"]) for d in item.documents]
    if references != retained or any(d.get("sha256") is None for d in item.documents):
        _fail("aste_checkpoint_invalid")
    docs = Documents(state="complete" if result.document_listing_present else "unavailable",
        items=tuple(Document(official_id=d["official_id"], title=d["title"], sha256=d["sha256"]) for d in item.documents))
    condition = [d["sha256"] for d in item.documents if d["title"].strip().casefold() == "condizioni d'asta"]
    category, proofs = _category(session, policy, item, now)
    bundle = json.loads(result.raw_bundle)
    bundle.update(category_evidence=proofs, documents=item.documents, detail_received_at=sources._utc(item.detail_at).isoformat(),
        status_received_at=now.isoformat())
    raw = sources._encoded(bundle)
    payload = result.facts.model_dump(mode="json")
    payload.update(category=category, documents=docs.model_dump(mode="json"),
        conditions_sha256=condition[0] if len(condition) == 1 else fingerprint(sorted(condition)) if condition else None,
        raw_sha256=hashlib.sha256(raw).hexdigest())
    facts = AuctionFacts.model_validate(payload)
    sources.accept_record(session, state.permission_id, raw, facts, request_key=state.lease_token,
        request_url=parser.detail_url(item.identifier), expected_generation=selected.generation,
        expected_cursor_version=selected.cursor_version, received_at=now, now=now)
    item.last_record_at, item.last_error = now, None
    item.next_check_at = now + timedelta(seconds=policy.min_poll_seconds)
    state.last_record_at = now
    _reset(item)


def succeed(session, ticket, raw, *, now):
    """Caller transaction commits page/checkpoint and journal changes together."""
    now = sources._clock(now)
    policy, selected, state = guard(session, ticket, now=now)
    if ticket["kind"] == "listing":
        _listing(session, policy, selected, state, ticket, raw, now)
    else:
        item = session.get(AsteItem, ticket["identifier"], populate_existing=True)
        if item is None or item.stage != ticket["kind"]:
            _fail("aste_checkpoint_invalid")
        if ticket["kind"] == "detail":
            _storage(session, len(raw))
            item.detail_payload, item.detail_at = raw, now
            item.payload_expires_at = now + timedelta(seconds=policy.raw_retention_seconds)
            item.stage = "status"
        elif ticket["kind"] in ("status", "admit"):
            if item.detail_payload is None:
                _fail("aste_checkpoint_invalid")
            result = parser.parse_detail(item.detail_payload, raw, identifier=item.identifier,
                now=now, max_age_seconds=policy.max_age_seconds)
            if ticket["kind"] == "status" and result.documents:
                minimum_window = (len(result.documents) + 1) * 2 * policy.native_access.request_interval_seconds
                if minimum_window > policy.max_age_seconds - (now - sources._utc(item.detail_at)).total_seconds():
                    _fail("aste_document_window_unavailable")
                item.documents = [{"official_id": d.official_id, "url": d.url, "title": d.title} for d in result.documents]
                item.document_index, item.stage = 0, "documents"
            else:
                _admit(session, policy, selected, state, item, result, now)
        elif ticket["kind"] == "documents":
            from .aste_transport import MAX_DOCUMENT_BYTES
            if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-") or len(raw) > MAX_DOCUMENT_BYTES:
                _fail("aste_document_invalid")
            if item.document_index != ticket["document_index"]:
                _fail("aste_checkpoint_invalid")
            docs = [dict(d) for d in item.documents]
            docs[item.document_index].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), received_at=now.isoformat())
            item.documents = docs
            item.document_index += 1
            if item.document_index == len(docs):
                item.stage = "admit"
        if item.stage != "detail":
            item.next_check_at = now
    state.lease_token, state.lease_until, state.lease_job = None, None, None
    session.flush()


def failed(session, ticket, code, *, now, retry_after_seconds=None):
    policy, _, state = guard(session, ticket, now=now)
    delay = max(policy.native_access.request_interval_seconds, 60, retry_after_seconds or 0)
    # Even an extremely long publisher wait cannot overflow or be shortened into
    # an early request. At source expiry future claims fail the permission gate.
    until_expiry = max(0, (policy.valid_until - now).total_seconds())
    state.next_request_at = now + timedelta(seconds=min(delay, until_expiry))
    state.last_error = code if isinstance(code, str) and code.startswith(("aste_", "auction_")) and len(code) <= 100 else "aste_collection_failed"
    if ticket.get("identifier"):
        item = session.get(AsteItem, ticket["identifier"])
        if item:
            item.last_error, item.next_check_at = state.last_error, state.next_request_at
            _reset(item)
    state.lease_token, state.lease_until, state.lease_job = None, None, None
    session.flush()


def cleanup(session, *, now, limit=500):
    """Purge only expired/revoked acquisition evidence, not private user decisions."""
    from .auction_source_models import AuctionSourcePermission
    _collector(session)  # Serialize payload expiry with checkpoint admission.
    expired = select(AuctionSourcePermission.id).where(
        (AuctionSourcePermission.revoked_at.is_not(None)) | (AuctionSourcePermission.valid_until <= now))
    rows = list(session.scalars(select(AsteItem).where(
        ((AsteItem.payload_expires_at <= now) | AsteItem.permission_id.in_(expired)),
        (AsteItem.detail_payload.is_not(None)) | (AsteItem.payload_expires_at.is_not(None))
        | (AsteItem.stage != "detail") | (cast(AsteItem.category_proofs, String) != "{}")).limit(limit)))
    revoked = set(session.scalars(expired.where(AuctionSourcePermission.id.in_({item.permission_id for item in rows}))))
    for item in rows:
        _reset(item)
        if item.permission_id in revoked:
            item.category_proofs = {}
    bodies = list(session.scalars(select(AsteListingEvidence).where(
        (AsteListingEvidence.raw_expires_at <= now) | AsteListingEvidence.permission_id.in_(expired))
        .where(AsteListingEvidence.raw_payload.is_not(None)).limit(limit)))
    for proof in bodies:
        proof.raw_payload = None
    ids = list(session.scalars(select(AsteListingEvidence.id).where(
        (AsteListingEvidence.normalized_expires_at <= now) | AsteListingEvidence.permission_id.in_(expired)).limit(limit)))
    if ids:
        session.execute(delete(AsteListingEvidence).where(AsteListingEvidence.id.in_(ids)))
    session.flush()
    return {"item_payloads": len(rows), "listing_payloads": len(bodies), "listing_proofs": len(ids)}
