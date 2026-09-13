"""Private source-bound warning history and consent-bound delivery intents.

Caller owns commit. Processing an already active monitor does not establish
source coverage; the lifecycle gate must independently prove readiness.
Official prose stays in the permission-bound journal, never in duplicated facts.
No network, monitor activation or SMTP occurs inside projection.
"""

from copy import deepcopy
from dataclasses import asdict
from typing import get_args

from sqlalchemy import func, or_, select, update

from .config import DomainError
from .hazard_contracts import Hazard
from .hazard_models import (
    HazardConfigurationRevision,
    HazardDevelopment,
    HazardEventRevision,
    HazardMonitor,
    HazardMute,
    HazardReviewAction,
)
from .hazard_repository import _version, configuration, owned
from .hazard_source_models import HazardCurrentWarning, HazardMessageEvidence
from .hazard_sources import (
    _clock,
    _encoded,
    _hash,
    _selection,
    _utc,
    classify,
    read_message,
    require_permission,
)
from .monitoring_subjects import _savepoint

MAX_DEVELOPMENTS = 1000
MAX_REVISIONS = 10000
MAX_PROOF_BYTES = 8192
MAX_REVIEW_ACTIONS = 10000
IMPORTANCE = {"information": 0, "warning": 1, "alarm": 2}


def _fail(code, status=409):
    raise DomainError("Private warning evidence is unavailable or changed.", status, code) from None


def _configuration(session, monitor, revision):
    row = session.scalar(select(HazardConfigurationRevision).where(
        HazardConfigurationRevision.monitor_id == monitor.id,
        HazardConfigurationRevision.organization_id == monitor.organization_id,
        HazardConfigurationRevision.revision == revision))
    if row is None:
        _fail("hazard_event_configuration_missing", 503)
    config = configuration(row.configuration)
    if row.configuration_hash != config.fingerprint():
        _fail("hazard_event_configuration_invalid", 503)
    return config


def _geography(store, config, now):
    proof = store.verify_location(config.location, now=now)
    if proof.get("state") != "verified":
        _fail("hazard_event_geography_unavailable")
    return {"version": proof["version"], "sha256": proof["sha256"]}


def _event(session, development, revision=None):
    row = session.scalar(select(HazardEventRevision).where(
        HazardEventRevision.development_id == development.id,
        HazardEventRevision.organization_id == development.organization_id,
        HazardEventRevision.revision == (development.revision if revision is None else revision))
        .execution_options(populate_existing=True))
    if row is None or row.permission_id != development.permission_id:
        _fail("hazard_event_missing", 404)
    if _hash(_encoded({"decision": row.decision, "proof": row.proof})) != row.fingerprint:
        _fail("hazard_event_invalid", 503)
    return row


def _decision(message, policy, config, store, now, previous):
    # CAP removal/all-clear addresses the exact prior lineage; a Cancel has no
    # area. It must never create a new affected-place event by itself.
    if message.state in {"cancelled", "resolved"}:
        return ({**deepcopy(previous), "state": message.state, "reason": "explicit_source_" + message.state}
                if previous else None)
    mapping = classify(message, policy)
    if not mapping["complete"]:
        return ({"state": "unavailable", "reason": "hazard_classification_unknown"} if previous else None)
    info = message.infos[0]
    matched = store.match_warning(info.areas, config.location, geocode_version=policy.geocode_version, now=now)
    base = {"hazards": mapping["hazards"], "importance": mapping["importance"], "certainty": info.certainty,
            "effective": info.effective.isoformat() if info.effective else None,
            "expires": info.expires.isoformat() if info.expires else None, "match": matched}
    if matched.get("state") not in {"match", "no_match"}:
        return ({"state": "unavailable", "reason": "hazard_location_match_unknown", **base} if previous else None)
    if (matched["state"] == "no_match" or not set(mapping["hazards"]).intersection(config.hazards)
            or IMPORTANCE[mapping["importance"]] < IMPORTANCE[config.minimum_importance]):
        return ({"state": "not_relevant", "reason": "outside_current_selection", **base} if previous else None)
    return {"state": "planned" if info.effective and info.effective > now else "active",
            "reason": "official_warning_for_saved_location", **base}


def project_message(session, user_id, monitor_id, permission_id, evidence_id, *, monitor_version,
                    source_generation, source_cursor, store, now):
    """Internal worker projection of one exact current head; never starts a draft."""
    now = _clock(now)
    _version(monitor_version)
    _version(source_generation)
    _version(source_cursor)
    monitor = owned(session, user_id, monitor_id, write=True)
    _, policy = require_permission(session, permission_id, now=now, purpose="matching")
    require_permission(session, permission_id, now=now, purpose="display")
    if not policy.private_decisions_allowed:
        _fail("hazard_private_decisions_denied", 403)
    selected = _selection(session, policy.source_key)
    if (selected is None or selected.permission_id != permission_id or selected.generation != source_generation
            or selected.cursor_version != source_cursor):
        _fail("hazard_event_source_changed")
    monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor.id,
        HazardMonitor.organization_id == monitor.organization_id, HazardMonitor.owner_user_id == user_id)
        .with_for_update().execution_options(populate_existing=True))
    if monitor.version != monitor_version or monitor.status != "active":
        _fail("hazard_event_monitor_inactive_or_changed")
    config = _configuration(session, monitor, monitor.revision)
    if config.model_dump(mode="json") != monitor.configuration or config.location.canton not in policy.covered_cantons:
        _fail("hazard_event_configuration_or_scope_invalid")
    message = read_message(session, permission_id, evidence_id, now=now, purpose="matching", fresh=True)
    evidence = session.get(HazardMessageEvidence, evidence_id, populate_existing=True)
    head = session.get(HazardCurrentWarning, (permission_id, evidence.development_key), populate_existing=True)
    if head is None or head.evidence_id != evidence_id or head.generation != source_generation:
        _fail("hazard_event_source_not_current")
    geo = _geography(store, config, now)
    development = session.scalar(select(HazardDevelopment).where(
        HazardDevelopment.monitor_id == monitor.id, HazardDevelopment.organization_id == monitor.organization_id,
        HazardDevelopment.configuration_revision == monitor.revision, HazardDevelopment.permission_id == permission_id,
        HazardDevelopment.source_development_key == evidence.development_key).execution_options(populate_existing=True))
    old = _event(session, development) if development else None
    decision = _decision(message, policy, config, store, now, old.decision if old else None)
    if decision is None:
        return {"changed": False, "development_id": None}
    matched = decision.get("match")
    if matched and (matched.get("boundary_version"), matched.get("boundary_sha256")) != (geo["version"], geo["sha256"]):
        _fail("hazard_event_geography_changed")
    proof = {"configuration_hash": config.fingerprint(), "source_hash": evidence.normalized_hash,
             "source_generation": source_generation, "source_material_sequence": evidence.material_sequence,
             "boundary": geo, "evidence_id": evidence_id}
    fingerprint = _hash(_encoded({"decision": decision, "proof": proof}))
    if old and old.fingerprint == fingerprint:
        return {"changed": False, "development_id": development.id, "revision": development.revision}
    material_hash = _hash(_encoded({"decision": decision, "source_material_sequence": evidence.material_sequence}))
    if len(_encoded({"decision": decision, "proof": proof})) > MAX_PROOF_BYTES:
        _fail("hazard_event_storage_limit")
    with _savepoint(session):
        count, revisions = session.execute(select(func.count(HazardEventRevision.id), func.count(func.distinct(HazardDevelopment.id)))
            .select_from(HazardDevelopment).outerjoin(HazardEventRevision, HazardEventRevision.development_id == HazardDevelopment.id)
            .where(HazardDevelopment.monitor_id == monitor.id)).one()
        if count >= MAX_REVISIONS or development is None and revisions >= MAX_DEVELOPMENTS:
            _fail("hazard_event_storage_limit")
        if development is None:
            development = HazardDevelopment(organization_id=monitor.organization_id, monitor_id=monitor.id,
                configuration_revision=monitor.revision, permission_id=permission_id,
                source_development_key=evidence.development_key, material_hash=material_hash)
            session.add(development)
            session.flush()
        else:
            development.revision += 1
            development.material_sequence += int(development.material_hash != material_hash)
            development.material_hash = material_hash
            development.version += 1
        session.add(HazardEventRevision(organization_id=monitor.organization_id, development_id=development.id,
            permission_id=permission_id, evidence_id=evidence_id, revision=development.revision,
            material_sequence=development.material_sequence, decision=decision, proof=proof,
            fingerprint=fingerprint, created_at=now))
        session.flush()
        if _geography(store, config, now) != geo:
            _fail("hazard_event_geography_changed")
        from .hazard_delivery import record_intent
        if old is None or old.material_sequence != development.material_sequence:
            record_intent(session, monitor, development, _event(session, development), store=store, now=now)
    return {"changed": True, "development_id": development.id, "revision": development.revision}


def _owned_development(session, user_id, monitor_id, development_id, *, write=False):
    monitor = owned(session, user_id, monitor_id, write=write)
    development = session.scalar(select(HazardDevelopment).where(HazardDevelopment.id == development_id,
        HazardDevelopment.monitor_id == monitor.id, HazardDevelopment.organization_id == monitor.organization_id)
        .execution_options(populate_existing=True))
    if development is None:
        _fail("hazard_event_missing", 404)
    return monitor, development


def read_event(session, user_id, monitor_id, development_id, *, store, now, revision=None):
    now = _clock(now)
    if revision is not None:
        _version(revision)
    monitor, development = _owned_development(session, user_id, monitor_id, development_id)
    summary = {"id": development.id, "monitor_id": monitor.id, "version": development.version,
               "revision": development.revision if revision is None else revision, "historical": revision is not None}
    try:
        _, policy = require_permission(session, development.permission_id, now=now, purpose="display")
        require_permission(session, development.permission_id, now=now, purpose="matching")
        if not policy.private_decisions_allowed:
            _fail("hazard_private_decisions_denied", 403)
        row = _event(session, development, revision)
        config = _configuration(session, monitor, development.configuration_revision)
        if row.proof.get("configuration_hash") != config.fingerprint() or _geography(store, config, now) != row.proof.get("boundary"):
            _fail("hazard_event_geography_changed")
        message = read_message(session, development.permission_id, row.evidence_id, now=now,
                               purpose="display", fresh=revision is None)
        evidence = session.get(HazardMessageEvidence, row.evidence_id, populate_existing=True)
        if (evidence.development_key != development.source_development_key
                or evidence.normalized_hash != row.proof.get("source_hash") or row.proof.get("evidence_id") != row.evidence_id):
            _fail("hazard_event_source_binding_invalid", 503)
        if revision is None:
            selected = _selection(session, policy.source_key)
            head = session.get(HazardCurrentWarning, (development.permission_id, development.source_development_key), populate_existing=True)
            if (monitor.status != "active" or monitor.revision != development.configuration_revision
                    or selected is None or selected.permission_id != development.permission_id
                    or selected.generation != row.proof.get("source_generation") or head is None
                    or head.evidence_id != row.evidence_id or head.generation != selected.generation):
                _fail("hazard_event_current_changed")
        reviewed = row.material_sequence <= development.reviewed_sequence
        dismissed = row.material_sequence <= development.dismissed_sequence
        muted_types = set(session.scalars(select(HazardMute.hazard).where(HazardMute.monitor_id == monitor.id,
            HazardMute.organization_id == monitor.organization_id, HazardMute.muted.is_(True))))
        selected_types = set(row.decision.get("hazards", ())).intersection(config.hazards)
        muted = bool(selected_types) and selected_types <= muted_types
        return {**summary, "state": row.decision["state"], "decision": deepcopy(row.decision),
                "reviewed": reviewed, "dismissed": dismissed, "material_sequence": row.material_sequence,
                "needs_review": not reviewed and not dismissed, "muted": muted, "source": {"attribution": policy.attribution,
                "message": asdict(message), "last_seen_at": _utc(evidence.last_seen_at).isoformat()}, "proof": deepcopy(row.proof)}
    except DomainError as error:
        if error.status == 404:
            raise
        return {**summary, "state": "unavailable", "reason": error.code}


def set_review(session, user_id, monitor_id, development_id, *, version, expected_revision, action, store, now):
    now = _clock(now)
    _version(version)
    _version(expected_revision)
    if action not in {"reviewed", "not_relevant"}:
        _fail("hazard_event_review_invalid", 422)
    _, development = _owned_development(session, user_id, monitor_id, development_id, write=True)
    current = read_event(session, user_id, monitor_id, development_id, store=store, now=now)
    if current["state"] == "unavailable" or current["version"] != version or current["revision"] != expected_revision:
        _fail("hazard_event_review_conflict")
    values = {"reviewed_sequence" if action == "reviewed" else "dismissed_sequence": development.material_sequence,
              "version": version + 1}
    with _savepoint(session):
        count = session.scalar(select(func.count()).select_from(HazardReviewAction).join(
            HazardEventRevision, HazardEventRevision.id == HazardReviewAction.event_revision_id)
            .join(HazardDevelopment, HazardDevelopment.id == HazardEventRevision.development_id)
            .where(HazardDevelopment.monitor_id == monitor_id))
        if count >= MAX_REVIEW_ACTIONS:
            _fail("hazard_review_history_limit")
        changed = session.execute(update(HazardDevelopment).where(HazardDevelopment.id == development.id,
            HazardDevelopment.organization_id == development.organization_id, HazardDevelopment.version == version)
            .values(**values).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail("hazard_event_review_conflict")
        row = _event(session, development)
        session.add(HazardReviewAction(organization_id=development.organization_id, event_revision_id=row.id,
                                      user_id=user_id, action=action, created_at=now))
        session.flush()
    return read_event(session, user_id, monitor_id, development_id, store=store, now=now)


def list_events(session, user_id, monitor_id, *, store, now, limit=20, after_id=None):
    monitor = owned(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 20:
        _fail("hazard_event_page_invalid", 422)
    query = select(HazardDevelopment).where(HazardDevelopment.monitor_id == monitor.id,
        HazardDevelopment.organization_id == monitor.organization_id, HazardDevelopment.configuration_revision == monitor.revision)
    if after_id is not None:
        _, cursor = _owned_development(session, user_id, monitor_id, after_id)
        if cursor.configuration_revision != monitor.revision:
            _fail("hazard_event_cursor_changed")
        query = query.where(HazardDevelopment.id > after_id)
    rows = list(session.scalars(query.order_by(HazardDevelopment.id).limit(limit + 1)))
    items = []
    for row in rows[:limit]:
        entry = read_event(session, user_id, monitor_id, row.id, store=store, now=now)
        entry.pop("source", None)
        entry.pop("proof", None)
        items.append(entry)
    return {"items": items, "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
            "coverage_verified": False}


def history(session, user_id, monitor_id, development_id, *, store, now, limit=20, before=None):
    monitor, development = _owned_development(session, user_id, monitor_id, development_id)
    if type(limit) is not int or not 1 <= limit <= 20:
        _fail("hazard_event_page_invalid", 422)
    query = select(HazardEventRevision.revision).where(HazardEventRevision.development_id == development.id,
                                                     HazardEventRevision.organization_id == monitor.organization_id)
    if before is not None:
        _version(before)
        if before > development.revision:
            _fail("hazard_event_cursor_changed")
        query = query.where(HazardEventRevision.revision < before)
    revisions = list(session.scalars(query.order_by(HazardEventRevision.revision.desc()).limit(limit + 1)))
    items = []
    for revision in revisions[:limit]:
        entry = read_event(session, user_id, monitor_id, development_id, store=store, now=now, revision=revision)
        entry.pop("source", None)
        entry.pop("proof", None)
        items.append(entry)
    return {"items": items, "next_cursor": revisions[limit - 1] if len(revisions) > limit else None}


def review_history(session, user_id, monitor_id, development_id, *, limit=20, before_id=None):
    monitor, development = _owned_development(session, user_id, monitor_id, development_id)
    if type(limit) is not int or not 1 <= limit <= 20:
        _fail("hazard_event_page_invalid", 422)
    query = select(HazardReviewAction, HazardEventRevision.revision, HazardEventRevision.material_sequence).join(
        HazardEventRevision, HazardEventRevision.id == HazardReviewAction.event_revision_id).where(
        HazardEventRevision.development_id == development.id, HazardReviewAction.organization_id == monitor.organization_id)
    if before_id is not None:
        cursor = session.execute(query.where(HazardReviewAction.id == before_id)).first()
        if cursor is None:
            _fail("hazard_review_cursor_invalid", 404)
        query = query.where(or_(HazardReviewAction.created_at < cursor[0].created_at,
            (HazardReviewAction.created_at == cursor[0].created_at) & (HazardReviewAction.id < before_id)))
    rows = list(session.execute(query.order_by(HazardReviewAction.created_at.desc(), HazardReviewAction.id.desc()).limit(limit + 1)))
    # Only the owner's minimal action audit is returned; no official or derived
    # source content survives here when its separate permission expires.
    return {"items": [{"id": action.id, "action": action.action, "revision": revision,
                       "material_sequence": sequence, "created_at": _utc(action.created_at).isoformat()}
                      for action, revision, sequence in rows[:limit]],
            "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None}


def mutes(session, user_id, monitor_id):
    monitor = owned(session, user_id, monitor_id)
    selected = list(session.scalars(select(HazardMute.hazard).where(HazardMute.monitor_id == monitor.id,
        HazardMute.organization_id == monitor.organization_id, HazardMute.muted.is_(True)).order_by(HazardMute.hazard)))
    return {"monitor_id": monitor.id, "version": monitor.version, "muted_hazards": selected}


def set_mute(session, user_id, monitor_id, hazard, *, version, muted, now):
    now = _clock(now)
    _version(version)
    monitor = owned(session, user_id, monitor_id, write=True)
    if type(muted) is not bool or hazard not in get_args(Hazard):
        _fail("hazard_mute_invalid", 422)
    if monitor.status == "archived" or monitor.version != version:
        _fail("hazard_mute_conflict")
    with _savepoint(session):
        changed = session.execute(update(HazardMonitor).where(HazardMonitor.id == monitor.id,
            HazardMonitor.organization_id == monitor.organization_id, HazardMonitor.owner_user_id == user_id,
            HazardMonitor.version == version, HazardMonitor.status != "archived")
            .values(version=version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail("hazard_mute_conflict")
        row = session.get(HazardMute, (monitor.id, hazard), populate_existing=True)
        if row is None:
            row = HazardMute(monitor_id=monitor.id, organization_id=monitor.organization_id, hazard=hazard)
            session.add(row)
        row.muted, row.changed_at = muted, now
        session.flush()
    return mutes(session, user_id, monitor_id)
