"""One owner's duplicate monitors share attention, never another owner's state."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_monitoring_runtime import NOW, input_sample, policy, seed
from test_monitoring_subjects import db as db
from test_pollen_delivery import Mailer

from helvetic_lens import monitoring_runtime as runtime
from helvetic_lens.models import User
from helvetic_lens.monitoring_live_models import MonitoringDelivery
from helvetic_lens.pollen_delivery import deliver


def duplicates(db):
    ids = [(seed(db, key="first"), "owner"), (seed(db, key="second"), "owner"),
           (seed(db, key="peer", user_id="peer"), "peer")]
    input_sample(db, "0")
    runs = []
    with db.session() as session:
        for subject_id, owner in ids:
            session.get(User, owner).email_verified_at = NOW
            started = runtime.command(session, settings=policy(), user_id=owner, subject_id=subject_id,
                action="start", expected_revision=1, expected_version=0, request_key="start", now=NOW, email_consent=True)
            runs.append(started["runtime"]["run_id"])
        session.commit()
    input_sample(db, "10", 1)
    with db.session() as session:
        for (subject_id, owner), run in zip(ids, runs):
            runtime.refresh_from_cache(session, settings=policy(), user_id=owner, subject_id=subject_id,
                run_id=run, now=NOW + timedelta(hours=1))
        session.commit()
    return ids


def test_today_deduplicates_and_four_review_states_preserve_each_private_history(db):
    ids = duplicates(db)
    with db.session() as session:
        today = runtime.today(session, settings=policy(), user_id="owner", now=NOW + timedelta(hours=1))
        assert len(today["items"]) == 1
        card = today["items"][0]
        for version, (decision, count) in enumerate([
            ("action_required", 1), ("reviewed", 0), ("continue", 1), ("not_relevant", 0)
        ]):
            runtime.review(session, user_id="owner", subject_id=card["subject_id"], entry_id=card["id"],
                decision=decision, expected_version=version)
            session.commit()
            assert len(runtime.today(session, settings=policy(), user_id="owner", now=NOW + timedelta(hours=1))["items"]) == count
            for subject_id, owner in ids[:2]:
                entry = runtime.history(session, user_id=owner, subject_id=subject_id, material_only=True)["items"][0]
                assert entry["review"] == {"version": version + 1, "decision": decision}
        peer = runtime.history(session, user_id="peer", subject_id=ids[2][0], material_only=True)["items"][0]
        assert peer["review"] is None
        assert len(runtime.today(session, settings=policy(), user_id="peer", now=NOW + timedelta(hours=1))["items"]) == 1


@pytest.mark.parametrize("ambiguous", [False, True])
def test_same_signal_sends_at_most_once_per_owner_even_after_ambiguous_smtp(db, ambiguous):
    ids, mailer = duplicates(db), Mailer(fail=ambiguous)
    now = NOW + timedelta(hours=1)
    result = deliver(db, policy(), subject_id=ids[0][0], consent_version=1, now=now, mailer=mailer)
    assert result["status"] == ("uncertain" if ambiguous else "sent")
    assert deliver(db, policy(), subject_id=ids[1][0], consent_version=1, now=now, mailer=mailer)["status"] == "no_eligible_changes"
    assert len(mailer.messages) == 1
    peer_mailer = Mailer()
    assert deliver(db, policy(), subject_id=ids[2][0], consent_version=1, now=now, mailer=peer_mailer)["status"] == "sent"
    assert len(peer_mailer.messages) == 1
    with db.session() as session:
        assert sorted(session.scalars(select(MonitoringDelivery.state))) == sorted([
            "uncertain" if ambiguous else "sent", "suppressed", "sent"])


def test_concurrent_duplicate_delivery_serializes_on_owner(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ids, mailer, start = duplicates(db), Mailer(), Barrier(2)
    def send(subject_id):
        start.wait(timeout=10)
        return deliver(db, policy(), subject_id=subject_id, consent_version=1,
            now=NOW + timedelta(hours=1), mailer=mailer)["status"]
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(send, [row[0] for row in ids[:2]]))
    assert sorted(results) == ["no_eligible_changes", "sent"]
    assert len(mailer.messages) == 1
