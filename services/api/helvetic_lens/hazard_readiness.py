"""Activation evidence for the explicitly selected warning source. No network."""

import re
from datetime import timedelta

from sqlalchemy import update

from .config import DomainError
from .hazard_native_source import permission_id as selected_permission_id
from .hazard_source_models import HazardSourceSelection
from .hazard_sources import _clock, _selection, _utc, require_permission


def fail(code):
    raise DomainError("Warning monitoring is not ready for this saved place.", 409, code)


def record_completed_poll(session, permission_id, *, generation, cursor, request_url, evidence_sha256, now):
    """Trusted collector only, after the complete permitted response is ingested.

    Empty successful polls may establish channel freshness, never all-clear.
    Receipt of a single CAP message cannot call this implicitly. The native
    adapter must hash the actual transport evidence; this is not an HTTP API.
    """
    now = _clock(now)
    _, policy = require_permission(session, permission_id, now=now)
    if (type(generation) is not int or generation < 1 or type(cursor) is not int or cursor < 0
            or request_url != policy.endpoint or not isinstance(evidence_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None):
        fail("hazard_poll_evidence_invalid")
    selected = _selection(session, policy.source_key)
    if (selected is None or selected.permission_id != permission_id or selected.generation != generation
            or selected.cursor_version != cursor or selected.last_poll_at and _utc(selected.last_poll_at) > now):
        fail("hazard_poll_source_changed")
    changed = session.execute(update(HazardSourceSelection).where(HazardSourceSelection.source_key == policy.source_key,
        HazardSourceSelection.permission_id == permission_id, HazardSourceSelection.generation == generation,
        HazardSourceSelection.cursor_version == cursor).values(last_poll_at=now, last_poll_hash=evidence_sha256,
            poll_cursor_version=cursor).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        fail("hazard_poll_source_changed")


def current_source(session, settings, *, now):
    now = _clock(now)
    if settings is None or not settings.hazard_watch_enabled or not settings.hazard_source_enabled:
        fail("hazard_source_not_configured")
    permission_id = selected_permission_id(session, settings)
    if not permission_id:
        fail("hazard_source_not_configured")
    permission, policy = require_permission(session, permission_id, now=now, purpose="matching")
    require_permission(session, permission_id, now=now, purpose="display")
    if not policy.private_decisions_allowed:
        fail("hazard_private_decisions_denied")
    selected = _selection(session, policy.source_key)
    if selected is None or selected.permission_id != permission_id:
        fail("hazard_source_selection_changed")
    if policy.protocol == "meteoalarm-v2" and (selected.feed_updated_at is None or not selected.feed_content_hash):
        fail("hazard_source_poll_not_current")
    if (selected.last_poll_at is None or selected.poll_cursor_version != selected.cursor_version
            or not selected.last_poll_hash or re.fullmatch(r"[0-9a-f]{64}", selected.last_poll_hash) is None
            or not timedelta(0) <= now - _utc(selected.last_poll_at) <= timedelta(seconds=policy.max_age_seconds)):
        fail("hazard_source_poll_not_current")
    return permission, policy, selected


def source_summary(session, settings, *, now):
    """Public channel status, never a saved-place coverage or all-clear claim."""
    now = _clock(now)
    try:
        _, policy, selected = current_source(session, settings, now=now)
    except DomainError as error:
        return {"state": "unavailable", "reason": error.code, "supported_hazards": []}
    return {"state": "current", "supported_hazards": [entry.hazard for entry in policy.coverage
        if entry.checked_at <= now < entry.valid_until], "attribution": policy.attribution,
        "last_poll_at": _utc(selected.last_poll_at).isoformat()}


def ready(session, settings, config, *, store, now):
    now = _clock(now)
    permission, policy, selected = current_source(session, settings, now=now)
    permission_id = permission.id
    geography = store.verify_location(config.location, now=now)
    if geography.get("state") != "verified":
        fail("hazard_location_not_verified")
    boundary = {"version": geography["version"], "sha256": geography["sha256"]}
    scope = []
    for hazard in config.hazards:
        coverage = next((entry for entry in policy.coverage if entry.hazard == hazard), None)
        if coverage is None or not coverage.checked_at <= now < coverage.valid_until:
            fail("hazard_selected_type_coverage_unverified")
        proof = store.verify_source_scope(config.location, coverage.cantons, now=now)
        if proof.get("state") != "verified":
            fail("hazard_source_location_scope_incomplete")
        if {"version": proof["version"], "sha256": proof["sha256"]} != boundary:
            fail("hazard_geography_changed")
        scope.append({"hazard": hazard, "evidence_sha256": coverage.evidence_sha256,
                      "valid_until": coverage.valid_until.isoformat()})
    return {"configuration_hash": config.fingerprint(), "permission_id": permission_id,
        "policy_hash": permission.policy_hash, "source_key": policy.source_key, "generation": selected.generation,
        "cursor": selected.cursor_version, "last_poll_at": _utc(selected.last_poll_at).isoformat(),
        "poll_evidence_sha256": selected.last_poll_hash, "boundary": boundary, "scope": scope}
