"""Negative filtering retains native source gates, positive lineage and privacy."""

import pytest
from sqlalchemy import event, func, select, update
from test_hazard_cap import NOW, info, message
from test_hazard_events import active_fixture
from test_hazard_events import store as store
from test_hazard_sources import accept, grant, revised
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.config import DomainError
from helvetic_lens.hazard_batch_projection import project_batch
from helvetic_lens.hazard_models import HazardDevelopment, HazardEventRevision
from helvetic_lens.hazard_source_models import HazardMessageEvidence
from helvetic_lens.models import OrganizationMembership

OUTSIDE = info(geometry="<circle>46.20,6.14 1</circle>")


def batch(session, monitor, permission, receipts, store, cursor, actor="owner"):
    return project_batch(session, actor, monitor, permission, [row["evidence_id"] for row in receipts],
        monitor_version=2, source_generation=1, source_cursor=cursor, store=store, now=NOW)


def test_negative_batch_has_fixed_query_cost_and_later_positive_and_outside_history(db, store):
    monitor, permission = active_fixture(db), grant(db, private_decisions_allowed=True)
    receipts = [accept(db, permission, message(identifier=f"negative-{index}", infos=OUTSIDE), cursor=index) for index in range(50)]
    counts = []
    for size in (1, 50):
        statements = []
        def counted(_connection, _cursor, statement, *_):
            statements.append(statement)
        with db.session() as session:
            event.listen(db.engine, "before_cursor_execute", counted)
            try:
                assert batch(session, monitor, permission, receipts[:size], store, 50) == {"changed": 0, "unavailable": 0}
            finally:
                event.remove(db.engine, "before_cursor_execute", counted)
            counts.append(len(statements))
            assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 0
            session.commit()
    assert counts[0] == counts[1] and counts[1] <= 16, counts
    positive = accept(db, permission, revised(identifier="positive", previous="negative-0"), cursor=50)
    with db.session() as session:
        assert batch(session, monitor, permission, [positive], store, 51)["changed"] == 1
        session.commit()
    outside = accept(db, permission, revised(identifier="outside", previous="positive",
        previous_sent="2026-09-13T09:30:00+00:00", sent="2026-09-13T09:45:00+00:00", infos=OUTSIDE), cursor=51)
    with db.session() as session:
        assert batch(session, monitor, permission, [outside], store, 52)["changed"] == 1
        decisions = list(session.scalars(select(HazardEventRevision.decision).order_by(HazardEventRevision.revision)))
        assert [row["state"] for row in decisions] == ["active", "not_relevant"]
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 1
        session.commit()


def test_negative_filter_does_not_hide_corrupt_evidence_or_missing_private_access(db, store):
    monitor, permission = active_fixture(db), grant(db, private_decisions_allowed=True)
    receipt = accept(db, permission, message(infos=OUTSIDE))
    with db.session() as session:
        with pytest.raises(DomainError):
            batch(session, monitor, permission, [receipt], store, 1, actor="viewer")
        session.get(HazardMessageEvidence, receipt["evidence_id"]).normalized_payload = b"corrupt"
        session.commit()
    with db.session() as session:
        assert batch(session, monitor, permission, [receipt], store, 1) == {"changed": 0, "unavailable": 1}
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 0


def test_even_an_empty_source_checks_access_and_accepts_its_real_zero_cursor(db, store):
    monitor, permission = active_fixture(db), grant(db, private_decisions_allowed=True)
    with db.session() as session:
        assert batch(session, monitor, permission, [], store, 0) == {"changed": 0, "unavailable": 0}
        with pytest.raises(DomainError):
            batch(session, monitor, permission, [], store, 0, actor="viewer")


def test_negative_batch_rechecks_membership_after_matching(db, store):
    monitor, permission = active_fixture(db), grant(db, private_decisions_allowed=True)
    receipt = accept(db, permission, message(infos=OUTSIDE))
    original = store.match_warning
    with db.session() as session:
        def changed_membership(*args, **kwargs):
            session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="viewer"))
            return original(*args, **kwargs)
        store.match_warning = changed_membership
        with pytest.raises(DomainError) as error:
            batch(session, monitor, permission, [receipt], store, 1)
        assert error.value.code == "subject_role_denied"
        session.rollback()
