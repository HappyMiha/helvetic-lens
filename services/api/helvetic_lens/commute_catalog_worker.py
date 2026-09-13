"""Durable shared catalogue renewal from one already verified cached archive.

Only imported public reference identities and known connections are considered.
No private monitor settings are read, changed or sent to a provider.
"""

import time
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import and_, literal, or_, select, union
from sqlalchemy.orm import aliased

from .commute_acquisition import AcquisitionError
from .commute_models import CommuteFeedState, CommuteInterchange, CommuteLegReference
from .commute_renewal import prepare_renewal, publish_renewal, resolve_renewal
from .commute_sources import SOURCES, read_feed
from .commute_static_collector import owned
from .transport_reference import ZURICH
from .transport_static import StaticArchive

BATCH_UNITS = 16  # At most 32 unique reference/date targets, including pair ends.
HORIZON_DAYS = 8
SCAN_SECONDS = 1200


def _state(saved, version, today):
    if not isinstance(saved, dict):
        raise AcquisitionError("static_renewal_cursor_invalid", blocked=True)
    if not saved or saved.get("version") != version:
        return {"version": version, "anchor": today.isoformat(), "offset": 0, "after": ["", ""], "complete": False}
    state = dict(saved)
    try:
        anchor = date.fromisoformat(state["anchor"])
        if (type(state["offset"]) is not int or not 0 <= state["offset"] < HORIZON_DAYS
                or type(state["complete"]) is not bool or len(state["after"]) != 2
                or any(not isinstance(value, str) or len(value) > 36 for value in state["after"])):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise AcquisitionError("static_renewal_cursor_invalid", blocked=True) from None
    if anchor > today:
        raise AcquisitionError("static_renewal_clock_regressed")
    if state["complete"] and anchor < today or (today - anchor).days >= HORIZON_DAYS:
        return _state({}, version, today)
    if anchor + timedelta(days=state["offset"]) < today:
        state.update(offset=(today - anchor).days, after=["", ""])
    return state


def _units(session, after):
    before_ref, after_ref = aliased(CommuteLegReference), aliased(CommuteLegReference)
    singles = select(CommuteLegReference.id.label("before_id"), literal("").label("after_id")).where(
        CommuteLegReference.enabled.is_(True))
    pairs = select(CommuteInterchange.from_reference_id, CommuteInterchange.to_reference_id).join(
        before_ref, before_ref.id == CommuteInterchange.from_reference_id).join(
        after_ref, after_ref.id == CommuteInterchange.to_reference_id).where(
        before_ref.enabled.is_(True), after_ref.enabled.is_(True))
    units = union(singles, pairs).subquery()
    return list(session.execute(select(units.c.before_id, units.c.after_id).where(
        or_(units.c.before_id > after[0], and_(units.c.before_id == after[0], units.c.after_id > after[1])))
        .order_by(units.c.before_id, units.c.after_id).limit(BATCH_UNITS + 1)))


def plan(session, saved, version, today):
    """Keyset pagination with exact service-day offsets, no private routes."""
    state = _state(saved, version, today)
    if state["complete"]:
        return state, None
    rows = _units(session, state["after"])
    if not rows:
        # Empty catalogue or a removed final page: advance the date, not a scan.
        if state["offset"] == HORIZON_DAYS - 1:
            state["complete"] = True
        else:
            state.update(offset=state["offset"] + 1, after=["", ""])
        return state, None
    selected = rows[:BATCH_UNITS]
    target_day = date.fromisoformat(state["anchor"]) + timedelta(days=state["offset"])
    requests, connections = set(), []
    for before, after in selected:
        reference = session.get(CommuteLegReference, before)
        if reference is None or not reference.enabled or not isinstance(reference.identity, dict):
            raise AcquisitionError("static_renewal_reference_invalid", blocked=True)
        offset = reference.identity.get("departure_day_offset")
        if type(offset) is not int or not -1 <= offset <= 7:
            raise AcquisitionError("static_renewal_reference_invalid", blocked=True)
        service_day = target_day - timedelta(days=offset)
        requests.add((before, service_day))
        if after:
            requests.add((after, service_day))
            connections.append((before, after, service_day))
    prepared = prepare_renewal(session, tuple(sorted(requests)), connection_requests=tuple(connections))
    if len(rows) > BATCH_UNITS:
        state["after"] = list(selected[-1])
    elif state["offset"] < HORIZON_DAYS - 1:
        state.update(offset=state["offset"] + 1, after=["", ""])
    else:
        state["complete"] = True
    return state, prepared


def renew_cached(database, settings, path, version, sha256, token, permissions, *, now, monotonic=time.monotonic):
    """Resolve outside transactions; commit catalogue and cursor together."""
    with database.session() as session:
        poll = owned(session, settings, token, permissions, now())
        state, prepared = plan(session, poll.renewal_state, version, now().astimezone(ZURICH).date())
    started, last_guard = monotonic(), None

    def checkpoint():
        nonlocal last_guard
        moment = monotonic()
        if moment - started >= SCAN_SECONDS:
            raise AcquisitionError("static_renewal_timeout")
        if last_guard is None or moment - last_guard >= 5:
            with database.session() as session:
                owned(session, settings, token, permissions, now())
            last_guard = moment

    resolved = None
    if prepared:
        with StaticArchive(path, expected_version=version, checkpoint=checkpoint) as archive:
            if archive.sha256 != sha256:
                raise AcquisitionError("static_checksum_conflict", blocked=True)
            resolved = resolve_renewal(archive, prepared)
        checkpoint()
    with database.session() as session:
        poll = owned(session, settings, token, permissions, now())
        # Lock feed rows after permission/poll locks; a source rotation must not
        # race the final version check and atomic catalogue/cursor publication.
        for source in SOURCES:
            session.scalar(select(CommuteFeedState).where(CommuteFeedState.source == source).with_for_update())
            _, permission, snapshot = read_feed(session, source, now=now(), require_fresh=True)
            if snapshot.feed_version != version or permission.id != permissions[source]:
                raise AcquisitionError("static_renewal_source_changed")
        if resolved:
            report = publish_renewal(session, prepared, resolved)
            state["last_outcomes"] = dict(Counter(item["status"] for item in report["items"]))
            state["last_connections"] = dict(Counter(item["state"] for item in report["interchanges"]))
            state["last_attempt_at"] = now().isoformat()
        poll.renewal_state = state
        session.commit()
    return {"state": "complete" if state["complete"] else "pending", "processed": len(prepared[0]) if prepared else 0}
