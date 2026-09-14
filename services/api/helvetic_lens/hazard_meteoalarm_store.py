"""Atomic native warning snapshot publication; caller owns commit.

Source presence is independent of official message state. Disappearance removes
current eligibility but never synthesizes a Cancel/AllClear or source revision.
All originals must validate before the completed-poll marker can be advanced.
"""

from datetime import timedelta

from sqlalchemy import select, update

from .hazard_cap import decode_cap, digest
from .hazard_meteoalarm import FEED_URL, TOTAL_SECONDS, verify_original
from .hazard_readiness import record_completed_poll
from .hazard_source_models import HazardCurrentWarning, HazardSourceSelection
from .hazard_sources import _clock, _error, _selection, _utc, accept_message, require_permission
from .monitoring_subjects import _savepoint


def publish(session, permission_id, snapshot, *, expected_generation, expected_cursor, now):
    now = _clock(now)
    started, completed = _clock(snapshot.started_at), _clock(snapshot.completed_at)
    _, policy = require_permission(session, permission_id, now=now)
    if (policy.protocol != "meteoalarm-v2" or policy.endpoint != FEED_URL
            or not policy.accepted_at <= started <= completed <= now
            or completed - started > timedelta(seconds=TOTAL_SECONDS)
            or now - started > timedelta(seconds=policy.max_age_seconds)):
        _error("meteoalarm_snapshot_invalid")
    selected = _selection(session, policy.source_key)
    if (selected is None or selected.permission_id != permission_id or selected.generation != expected_generation
            or type(expected_generation) is not int or type(expected_cursor) is not int):
        _error("hazard_source_selection_conflict")
    if (len(snapshot.originals) != len(snapshot.feed.warnings)
            or {o.warning for o in snapshot.originals} != set(snapshot.feed.warnings)
            or len(set(snapshot.feed.warnings)) != len(snapshot.feed.warnings)):
        _error("meteoalarm_incomplete_snapshot")
    decoded = []
    for original in snapshot.originals:
        if verify_original(original.warning, original.payload) != original:
            _error("meteoalarm_original_hash_changed")
        message = decode_cap(original.payload, received_at=completed, profile=policy.protocol)
        if message.unsupported:
            _error("hazard_unsupported_contract")
        decoded.append((message.identity.sent, message.identity.key, original))
    fingerprint = digest({"feed": snapshot.feed.evidence_sha256,
                          "originals": sorted((o.warning.url, o.evidence_sha256) for o in snapshot.originals)})
    if (selected.last_poll_at is not None and _utc(selected.last_poll_at) == completed
            and selected.last_poll_hash == fingerprint):
        return {"state": "published", "cursor": selected.cursor_version, "replay": True}
    if selected.cursor_version != expected_cursor:
        _error("hazard_source_cursor_conflict")
    if selected.feed_updated_at is not None:
        if snapshot.feed.updated < _utc(selected.feed_updated_at):
            _error("meteoalarm_feed_rollback")
        if (snapshot.feed.updated == _utc(selected.feed_updated_at)
                and snapshot.feed.evidence_sha256 != selected.feed_content_hash):
            _error("meteoalarm_feed_version_conflict")
    cursor, present = expected_cursor, set()
    with _savepoint(session):
        for _, _, original in sorted(decoded):
            result = accept_message(session, permission_id, original.payload,
                request_key=digest((completed.isoformat(), original.warning.url)), request_url=FEED_URL,
                expected_generation=expected_generation, expected_cursor_version=cursor, received_at=completed, now=now)
            cursor = result["cursor_version"]
            present.add(result["evidence_id"])
        heads = list(session.scalars(select(HazardCurrentWarning).where(
            HazardCurrentWarning.permission_id == permission_id,
            HazardCurrentWarning.generation == expected_generation).with_for_update()))
        for head in heads:
            head.present = head.evidence_id in present
        # Advance even for an empty/same-content poll: private work must detect
        # a new source snapshot while keeping material review sequence unchanged.
        changed = session.execute(update(HazardSourceSelection).where(
            HazardSourceSelection.source_key == policy.source_key,
            HazardSourceSelection.permission_id == permission_id, HazardSourceSelection.generation == expected_generation,
            HazardSourceSelection.cursor_version == cursor).values(cursor_version=cursor + 1,
                feed_updated_at=snapshot.feed.updated, feed_content_hash=snapshot.feed.evidence_sha256)
            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _error("hazard_source_cursor_conflict")
        session.flush()
        record_completed_poll(session, permission_id, generation=expected_generation, cursor=cursor + 1,
                              request_url=FEED_URL, evidence_sha256=fingerprint, now=completed)
    return {"state": "published", "cursor": cursor + 1, "replay": False,
            "present": sum(head.present for head in heads), "originals": len(snapshot.originals)}
