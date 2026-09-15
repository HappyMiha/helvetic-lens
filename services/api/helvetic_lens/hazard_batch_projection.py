"""Bounded negative filtering before the canonical private warning projector.

Only a never-seen warning with no native decision can skip per-event projection.
Existing developments and positive decisions retain the complete canonical path.
The caller owns an enclosing savepoint and final readiness/publication check.
"""

from sqlalchemy import select
from sqlalchemy.orm import defer

from .config import DomainError
from .hazard_events import MAX_DEVELOPMENTS, _configuration, _decision, _fail, _geography, project_message
from .hazard_models import HazardDevelopment, HazardMonitor
from .hazard_reconciliation import MAX_MESSAGES
from .hazard_repository import _version, owned
from .hazard_source_models import HazardCurrentWarning, HazardMessageEvidence
from .hazard_sources import _clock, _read_retained, _selection, require_permission

UNAVAILABLE = {"hazard_evidence_unavailable", "hazard_evidence_stale", "hazard_warning_period_expired",
    "hazard_source_poll_not_current", "hazard_source_no_longer_listed"}


def project_batch(session, user_id, monitor_id, permission_id, evidence_ids, *, monitor_version,
                  source_generation, source_cursor, store, now):
    now = _clock(now)
    for version in (monitor_version, source_generation):
        _version(version)
    if type(source_cursor) is not int or source_cursor < (1 if evidence_ids else 0):
        _fail("hazard_version_invalid", 422)
    if len(evidence_ids) > MAX_MESSAGES or len(set(evidence_ids)) != len(evidence_ids):
        _fail("hazard_source_batch_limit")
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
    geography = _geography(store, config, now)
    existing = set(session.scalars(select(HazardDevelopment.source_development_key).where(
        HazardDevelopment.monitor_id == monitor.id, HazardDevelopment.organization_id == monitor.organization_id,
        HazardDevelopment.configuration_revision == monitor.revision, HazardDevelopment.permission_id == permission_id)
        .limit(MAX_DEVELOPMENTS + 1)))
    if len(existing) > MAX_DEVELOPMENTS:
        _fail("hazard_event_storage_limit")
    rows = {evidence.id: (evidence, head) for evidence, head in session.execute(
        select(HazardMessageEvidence, HazardCurrentWarning).outerjoin(HazardCurrentWarning,
            (HazardCurrentWarning.permission_id == HazardMessageEvidence.permission_id)
            & (HazardCurrentWarning.development_key == HazardMessageEvidence.development_key))
        .where(HazardMessageEvidence.permission_id == permission_id, HazardMessageEvidence.id.in_(evidence_ids))
        .options(defer(HazardMessageEvidence.raw_payload)).execution_options(populate_existing=True))}
    changed = unavailable = 0
    for evidence_id in evidence_ids:
        evidence, head = rows.get(evidence_id, (None, None))
        try:
            message = _read_retained(evidence, policy, now=now, fresh=True, selected=selected, head=head)
            if head is None or head.evidence_id != evidence_id or head.generation != source_generation:
                _fail("hazard_event_source_not_current")
            if evidence.development_key not in existing and _decision(message, policy, config, store, now, None) is None:
                continue
            result = project_message(session, user_id, monitor_id, permission_id, evidence_id,
                monitor_version=monitor_version, source_generation=source_generation, source_cursor=source_cursor,
                store=store, now=now)
            changed += int(result["changed"])
        except DomainError as error:
            if error.code not in UNAVAILABLE:
                raise
            unavailable += 1
    # No cache crosses this transaction. Recheck actor and boundary even for an
    # entirely negative batch; the worker also rechecks its full source proof.
    owned(session, user_id, monitor_id, write=True)
    if _geography(store, config, now) != geography:
        _fail("hazard_event_geography_changed")
    return {"changed": changed, "unavailable": unavailable}
