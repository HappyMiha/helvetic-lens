"""Synthetic isolated delivery boundary; test doubles never contact SMTP."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from test_monitoring_runtime import command, input_sample, policy, refresh, seed
from test_monitoring_subjects import db as db
from test_pollen_thresholds import NOW

from helvetic_lens import monitoring_runtime as runtime
from helvetic_lens.models import User
from helvetic_lens.monitoring_live_models import MonitoringDelivery
from helvetic_lens.pollen_contracts import PollenConfiguration
from helvetic_lens.pollen_delivery import deliver, enqueue_due, next_delivery_at


def configuration(mode="immediate", digest=None, quiet=None):
    return PollenConfiguration(station_id="PBS", selections=[{"allergen": "grasses"}],
                               delivery={"email": mode, "digest_at": digest, "quiet_hours": quiet})


@pytest.mark.parametrize("clock, expected", [
    ("2026-03-29T00:00:00+00:00", "2026-03-29T01:00:00+00:00"),  # 02:30 is in the spring gap.
    ("2026-10-25T00:00:00+00:00", "2026-10-25T00:30:00+00:00"),  # First 02:30 only.
    ("2026-10-25T00:45:00+00:00", "2026-10-26T01:30:00+00:00"),  # Never schedule the repeated 02:30.
])
def test_daily_digest_dst_gap_and_repeated_clock(clock, expected):
    assert next_delivery_at(configuration("daily_digest", "02:30"), datetime.fromisoformat(clock)) == datetime.fromisoformat(expected)


@pytest.mark.parametrize("clock, expected", [
    ("2026-09-11T19:59:00+00:00", "2026-09-11T19:59:00+00:00"),
    ("2026-09-11T20:00:00+00:00", "2026-09-12T05:00:00+00:00"),
    ("2026-09-12T04:59:59+00:00", "2026-09-12T05:00:00+00:00"),
    ("2026-09-12T05:00:00+00:00", "2026-09-12T05:00:00+00:00"),
])
def test_overnight_quiet_hours_boundaries(clock, expected):
    config = configuration(quiet={"start": "22:00", "end": "07:00"})
    assert next_delivery_at(config, datetime.fromisoformat(clock)) == datetime.fromisoformat(expected)


class Mailer:
    def __init__(self, fail=False):
        self.messages, self.fail = [], fail

    def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))
        if self.fail:
            raise TimeoutError("synthetic ambiguous SMTP response")
        return "smtp"


def prepared(db):
    subject_id = seed(db)
    input_sample(db, "0")
    run_id = command(db, subject_id, consent=True)["runtime"]["run_id"]
    input_sample(db, "10", 1)
    refresh(db, subject_id, run_id, 1)
    with db.session() as session:
        user = session.get(User, "owner")
        user.email_verified_at = NOW
        session.commit()
    return subject_id


@pytest.mark.parametrize("instance", ["main", "monitoring-v2"])
def test_delivery_rechecks_and_sends_once_with_no_raw_source_in_email(db, instance):
    subject_id, mailer = prepared(db), Mailer()
    settings = policy()
    settings.deployment_instance = instance
    assert enqueue_due(db, settings, now=NOW + timedelta(hours=1))["enqueued"] == 1
    assert enqueue_due(db, settings, now=NOW + timedelta(hours=1))["enqueued"] == 0
    assert deliver(db, settings, subject_id=subject_id, consent_version=1,
                   now=NOW + timedelta(hours=1), mailer=mailer)["status"] == "sent"
    assert deliver(db, settings, subject_id=subject_id, consent_version=1,
                   now=NOW + timedelta(hours=1), mailer=mailer)["status"] == "no_eligible_changes"
    assert len(mailer.messages) == 1
    assert "number/m3" not in mailer.messages[0][0][2]


@pytest.mark.parametrize("withdrawal", ["unsubscribe", "pause", "reviewed", "source"])
def test_prepared_delivery_rechecks_consent_review_and_source(db, withdrawal):
    subject_id, mailer, settings = prepared(db), Mailer(), policy()
    if withdrawal in {"unsubscribe", "pause"}:
        command(db, subject_id, withdrawal, version=1, hour=1)
    elif withdrawal == "reviewed":
        with db.session() as session:
            entry = runtime.history(session, user_id="owner", subject_id=subject_id, material_only=True)["items"][0]
            runtime.review(session, user_id="owner", subject_id=subject_id, entry_id=entry["id"],
                           decision="reviewed", expected_version=0)
            session.commit()
    else:
        settings = settings.model_copy(update={"pollen_source_policy": settings.pollen_source_policy.model_copy(update={"channels": ()})})
    assert deliver(db, settings, subject_id=subject_id, consent_version=1,
                   now=NOW + timedelta(hours=1), mailer=mailer)["status"] == "no_eligible_changes"
    assert not mailer.messages
    with db.session() as session:
        assert session.scalar(select(MonitoringDelivery.state)) == "suppressed"


def test_ambiguous_smtp_send_is_retained_and_never_automatically_resent(db):
    subject_id, mailer = prepared(db), Mailer(fail=True)
    assert deliver(db, policy(), subject_id=subject_id, consent_version=1,
                   now=NOW + timedelta(hours=1), mailer=mailer)["status"] == "uncertain"
    assert deliver(db, policy(), subject_id=subject_id, consent_version=1,
                   now=NOW + timedelta(hours=1), mailer=mailer)["status"] == "no_eligible_changes"
    assert len(mailer.messages) == 1
    with db.session() as session:
        assert session.scalar(select(MonitoringDelivery.state)) == "uncertain"
