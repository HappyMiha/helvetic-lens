"""Internal reviewed source permission and bounded latest-feed storage.

No source credentials, HTTP acquisition or permission-write API. Permission
records must come from the operator's real source-access review, never a monitor.
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select

from .commute_models import CommuteFeedState, CommuteSourcePermission
from .config import DomainError
from .monitoring_subjects import _savepoint
from .transport_feed import ALERTS, TRIPS, decode_feed

SOURCES = (TRIPS, ALERTS)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def clock(now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware transport clock")
    return now.astimezone(UTC)


def record_permission(session, *, source, policy_reference, accepted_at, valid_until, max_age_seconds):
    accepted_at, valid_until = clock(accepted_at), clock(valid_until)
    if (source not in SOURCES or not isinstance(policy_reference, str) or not policy_reference.strip()
            or len(policy_reference) > 500 or valid_until <= accepted_at
            or type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600):
        raise ValueError("Record explicit reviewed source scope, validity and freshness")
    row = CommuteSourcePermission(source=source, policy_reference=policy_reference,
        accepted_at=accepted_at, valid_until=valid_until, max_age_seconds=max_age_seconds)
    session.add(row)
    session.flush()
    return row.id


def require_permission(session, permission_id, source, *, now):
    row = session.scalar(select(CommuteSourcePermission).where(CommuteSourcePermission.id == permission_id)
                         .with_for_update().execution_options(populate_existing=True))
    if (row is None or row.source != source or row.revoked_at is not None
            or not utc(row.accepted_at) <= now < utc(row.valid_until)):
        raise DomainError("Transport source permission is unavailable.", 409, "commute_source_permission_unavailable")
    return row


def accept_feed(session, permission_id, payload, *, now=None):
    now = clock(now)
    permission = session.get(CommuteSourcePermission, permission_id, populate_existing=True)
    if permission is None:
        raise DomainError("Transport source permission is unavailable.", 409, "commute_source_permission_unavailable")
    require_permission(session, permission_id, permission.source, now=now)
    snapshot = decode_feed(payload, source=permission.source, received_at=now)
    with _savepoint(session):
        state = session.scalar(select(CommuteFeedState).where(CommuteFeedState.source == permission.source)
                               .with_for_update().execution_options(populate_existing=True))
        if state is not None and state.permission_id == permission_id:
            if snapshot.observed_at < utc(state.observed_at):
                return "older"
            if snapshot.observed_at == utc(state.observed_at):
                if snapshot.sha256 != state.content_hash:
                    raise DomainError("Conflicting transport feed timestamp.", 409, "commute_feed_conflict")
                # Receipt time cannot freshen an unchanged source timestamp.
                return "replay"
        values = dict(permission_id=permission_id, received_at=now, observed_at=snapshot.observed_at,
                      static_version=snapshot.feed_version, content_hash=snapshot.sha256, content=payload)
        if state is None:
            session.add(CommuteFeedState(source=permission.source, generation=1, **values))
        else:
            state.generation += 1
            for name, value in values.items():
                setattr(state, name, value)
        session.flush()
    return "accepted"


def read_feed(session, source, *, now, require_fresh=False):
    row = session.get(CommuteFeedState, source, populate_existing=True)
    if row is None:
        raise DomainError("Transport source has no verified feed.", 409, "commute_feed_unavailable")
    permission = require_permission(session, row.permission_id, source, now=now)
    if hashlib.sha256(row.content).hexdigest() != row.content_hash:
        raise DomainError("Transport feed evidence is inconsistent.", 503, "commute_feed_invalid")
    try:
        snapshot = decode_feed(row.content, source=source, received_at=utc(row.received_at))
    except ValueError:
        raise DomainError("Transport feed evidence is inconsistent.", 503, "commute_feed_invalid") from None
    if snapshot.feed_version != row.static_version or snapshot.observed_at != utc(row.observed_at):
        raise DomainError("Transport feed metadata is inconsistent.", 503, "commute_feed_invalid")
    if snapshot.observed_at > now or utc(row.received_at) > now:
        raise DomainError("Transport feed is ahead of the current clock.", 409, "commute_feed_future")
    if require_fresh and (now - snapshot.observed_at).total_seconds() > permission.max_age_seconds:
        raise DomainError("Transport feed is stale.", 409, "commute_feed_stale")
    return row, permission, snapshot
