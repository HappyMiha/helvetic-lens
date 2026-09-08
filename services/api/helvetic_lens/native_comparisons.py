"""Persist explicit native baselines and consume exact complete saved diffs.

Internal application boundary. Caller owns the transaction and authorizes any
user-facing mutation. No source fetching, inference, commits or chronology guesses.
Selections are organization-local; a corpus-wide event never inherits one tenant's
baseline. Saved comparisons remain available when a selection changes or clears.
"""

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import DomainError
from .corpus_access import visible
from .db import utcnow
from .diffing import DIFF_SCHEMA_VERSION, compare_passages
from .interest_assessment import fingerprint
from .interest_material import plan
from .models import (
    NativeDocumentComparison,
    NativeEventComparisonSelection,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
)


def unavailable():
    raise DomainError("The native comparison or its exact source assignment is unavailable; select and rebuild it.",
                      409, "interest_comparison_unavailable")


def _event(session, organization_id, event_id):
    event = session.scalar(select(RegulatoryEvent)
        .join(RegulatoryEventState, RegulatoryEventState.event_id == RegulatoryEvent.id)
        .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
        .where(RegulatoryEvent.id == event_id, RegulatoryEventState.organization_id == organization_id,
               visible(RegulatoryWork, organization_id)))
    if event is None:
        raise DomainError("The event is not admitted to this organization.", 404, "not_found")
    return event


def _pair(session, organization_id, event, before_id, after_id):
    from .interest_admission import _saved_document
    if not event.expression_id or event.document_version_id != after_id or before_id == after_id:
        unavailable()
    expression = session.scalar(select(RegulatoryExpression).where(
        RegulatoryExpression.id == event.expression_id, RegulatoryExpression.work_id == event.work_id))
    if expression is None or expression.language.strip().lower() in {"", "und", "unknown"}:
        unavailable()
    old_native, before, old_binding = _saved_document(session, organization_id, before_id,
        event.work_id, "event", event.expression_id)
    new_native, after, new_binding = _saved_document(session, organization_id, after_id,
        event.work_id, "event", event.expression_id)
    # The legacy path has its own artifact identity confirmation and selected
    # watch baseline. Do not bypass those checks through a new native wrapper.
    if old_native.legacy_version_id or new_native.legacy_version_id:
        unavailable()
    binding = {"before": old_binding, "after": new_binding, "work": event.work_id,
               "expression": expression.id, "language": expression.language,
               "schema_version": DIFF_SCHEMA_VERSION}
    return before, after, binding


def _insert(session, model):
    return (pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert)(model)


def selection(session, organization_id, event_id):
    """Internal scoped read; external readers must also authorize current event access."""
    return session.scalar(select(NativeEventComparisonSelection).where(
        NativeEventComparisonSelection.organization_id == organization_id,
        NativeEventComparisonSelection.event_id == event_id).execution_options(populate_existing=True))


def select_baseline(session, organization_id, event_id, *, before_version_id, after_version_id,
                    expected_revision):
    """Select/clear an exact saved pair with optimistic concurrency (0 = absent).

    before_version_id=None explicitly clears selection; its revision tombstone is
    retained so an old editor cannot overwrite a subsequent choice. This selects
    comparison direction only, never asserts which version was legally in force.
    The complete deterministic diff is saved even if too large for a brief.
    """
    if type(expected_revision) is not int or expected_revision < 0:
        raise DomainError("A non-negative selection revision is required.", 422, "invalid_revision")
    if before_version_id is not None and (not isinstance(before_version_id, str) or not before_version_id.strip()):
        raise DomainError("Choose a saved baseline ID, or null to clear it.", 422, "invalid_baseline")
    session.flush()
    session.expire_all()
    event = _event(session, organization_id, event_id)
    # Also authorize current evidence on clear; retargeted events are not the
    # snapshot the editor saw. Clearing does not erase saved comparison history.
    from .interest_admission import _saved_document
    native, _, _ = _saved_document(session, organization_id, event.document_version_id,
        event.work_id, "event", event.expression_id)
    if native.legacy_version_id or native.id != after_version_id:
        unavailable()
    current = selection(session, organization_id, event_id)
    if (current.revision if current else 0) != expected_revision:
        raise DomainError("The baseline choice changed. Reload it before saving.", 409, "native_selection_conflict")
    pair = _pair(session, organization_id, event, before_version_id, after_version_id) if before_version_id else None
    comparison, key, diff = None, None, None
    if pair:
        before, after, binding = pair
        key = fingerprint(binding)
        comparison = session.scalar(select(NativeDocumentComparison).where(
            NativeDocumentComparison.organization_id == organization_id,
            NativeDocumentComparison.old_version_id == before.id,
            NativeDocumentComparison.new_version_id == after.id,
            NativeDocumentComparison.input_fingerprint == key))
        if comparison is None:
            diff = compare_passages(before.passages, after.passages)
    # Legacy sqlite3 transaction control does not BEGIN on SELECT/SAVEPOINT.
    # Without an explicit outer transaction RELEASE would commit the selection
    # even if the caller later rolls back. Acquire its write transaction only
    # after the expensive diff; CAS still decides which concurrent editor wins.
    connection = session.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    with session.begin_nested():
        comparison_id = None
        if pair:
            if comparison is None:
                session.execute(_insert(session, NativeDocumentComparison).values(
                    id=str(uuid4()), organization_id=organization_id, old_version_id=before.id,
                    new_version_id=after.id, input_fingerprint=key,
                    diff=diff, created_at=utcnow()
                ).on_conflict_do_nothing(index_elements=["organization_id", "old_version_id", "new_version_id", "input_fingerprint"]))
                comparison = session.scalar(select(NativeDocumentComparison).where(
                    NativeDocumentComparison.organization_id == organization_id,
                    NativeDocumentComparison.old_version_id == before.id,
                    NativeDocumentComparison.new_version_id == after.id,
                    NativeDocumentComparison.input_fingerprint == key))
            comparison_id = comparison.id
        unchanged = current is not None and current.comparison_id == comparison_id
        # A repeated save of identical inputs must not invalidate a reusable AI
        # brief. Still execute the CAS so a racing different selection wins safely.
        values = dict(comparison_id=comparison_id,
                      revision=expected_revision if unchanged else expected_revision + 1,
                      updated_at=utcnow())
        if expected_revision == 0:
            statement = _insert(session, NativeEventComparisonSelection).values(
                id=str(uuid4()), organization_id=organization_id, event_id=event_id, **values
            ).on_conflict_do_nothing(index_elements=["organization_id", "event_id"])
        else:
            statement = update(NativeEventComparisonSelection).where(
                NativeEventComparisonSelection.organization_id == organization_id,
                NativeEventComparisonSelection.event_id == event_id,
                NativeEventComparisonSelection.revision == expected_revision).values(**values)
        changed = session.scalar(statement.returning(NativeEventComparisonSelection.id))
        if changed is None:
            raise DomainError("The baseline choice changed. Reload it before saving.", 409, "native_selection_conflict")
    return selection(session, organization_id, event_id)


def event_material(session, organization_id, event):
    """None means no explicit native comparison; a stale selection fails closed."""
    _event(session, organization_id, event.id)
    chosen = selection(session, organization_id, event.id)
    if chosen is None or chosen.comparison_id is None:
        return None
    comparison = session.scalar(select(NativeDocumentComparison).where(
        NativeDocumentComparison.id == chosen.comparison_id,
        NativeDocumentComparison.organization_id == organization_id))
    if comparison is None:
        unavailable()
    before, after, binding = _pair(session, organization_id, event,
        comparison.old_version_id, comparison.new_version_id)
    if comparison.input_fingerprint != fingerprint(binding):
        unavailable()
    evidence, context = plan(comparison, before, after)
    context = context.model_copy(update={"basis": "organization_selected"})
    return evidence, {**binding, "selection": [chosen.id, chosen.revision],
                      "comparison": [comparison.id, context.diff_fingerprint]}, context
