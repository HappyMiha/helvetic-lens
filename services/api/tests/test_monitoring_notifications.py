"""Private notification cursors and exact Pollen evidence under later changes."""

from datetime import timedelta
from uuid import uuid4

import pytest
from test_monitoring_centre import centre as centre
from test_monitoring_runtime import NOW, command, input_sample, policy, refresh, seed
from test_river_today import change, monitor
from test_tender_repository import db as db
from test_tender_repository import template as template
from test_today_counts import enabled

from helvetic_lens import monitoring_notifications as notifications
from helvetic_lens import monitoring_runtime as pollen
from helvetic_lens.config import DomainError
from helvetic_lens.prompt_settings import PromptSettings


def test_private_cursor_empty_continuation_cannot_change_owner_domain_or_workspace(db):
    settings = enabled()
    with db.session() as session:
        row = monitor(session)
        ids = {change(session, row, sequence=n).id for n in range(1, 24)}
        session.commit()
    with db.session() as session:
        first = notifications.page(session, settings, "owner", domain="river", now=NOW, prompts=PromptSettings())
        assert len(first["items"]) == 20 and first["next_cursor"]
        second = notifications.page(session, settings, "owner", domain="river", now=NOW,
                                    prompts=PromptSettings(), cursor=first["next_cursor"])
        assert {item["id"] for item in first["items"] + second["items"]} == ids
        assert second["next_cursor"] is None
        for user, domain in (("peer", "river"), ("owner", "air")):
            with pytest.raises(DomainError) as error:
                notifications.page(session, settings, user, domain=domain, now=NOW,
                                   prompts=PromptSettings(), cursor=first["next_cursor"])
            assert error.value.code == "monitoring_notification_cursor_invalid"
    with db.organization_context("org-b"), db.session() as session, pytest.raises(DomainError):
        notifications.page(session, settings, "owner", domain="river", now=NOW,
                           prompts=PromptSettings(), cursor=first["next_cursor"])


@pytest.mark.parametrize("position", [None, [], 3, True, "bad-id", {"before": "2026-09-14", "before_id": str(uuid4())},
                                      {"before": "2026-09-14T00:00:00Z", "before_id": "invalid"}])
def test_malformed_native_position_is_rejected_before_reader(db, position):
    with db.session() as session, pytest.raises(DomainError) as error:
        token = notifications._encode(position, ["org-a", "owner", "river"]) if position is not None else "broken!"
        notifications.page(session, enabled(), "owner", domain="river", cursor=token, now=NOW, prompts=PromptSettings())
    assert error.value.code == "monitoring_notification_cursor_invalid"


def test_pollen_exact_entry_does_not_turn_into_latest_or_review_it(db):
    subject = seed(db)
    input_sample(db, "0")
    started = command(db, subject)
    input_sample(db, "10", 1)
    refresh(db, subject, started["runtime"]["run_id"], 1)
    at = NOW + timedelta(hours=1)
    with db.session() as session:
        item, = notifications.page(session, enabled(policy()), "owner", domain="pollen", now=at, prompts=PromptSettings())["items"]
        assert item["href"] == f"/pollen-watch?entry={item['id']}#draft={subject}"
        first = pollen.exact_entry(session, settings=policy(), user_id="owner", subject_id=subject, entry_id=item["id"], now=at)
        assert first["entry"]["current"]["value"] == "10"
        assert first["current_configuration"] and not first["newer_available"]
    input_sample(db, "0", 2)
    refresh(db, subject, started["runtime"]["run_id"], 2)
    with db.session() as session:
        retained = pollen.exact_entry(session, settings=policy(), user_id="owner", subject_id=subject,
                                     entry_id=item["id"], now=NOW + timedelta(hours=2))
        assert retained["entry"] == first["entry"] and retained["newer_available"]
        pollen.review(session, user_id="owner", subject_id=subject, entry_id=item["id"], decision="reviewed", expected_version=0)
        session.commit()
        latest, = notifications.page(session, enabled(policy()), "owner", domain="pollen",
                                     now=NOW + timedelta(hours=2), prompts=PromptSettings())["items"]
        assert latest["id"] != item["id"]
        with pytest.raises(DomainError):
            pollen.exact_entry(session, settings=policy(), user_id="peer", subject_id=subject, entry_id=item["id"], now=at)
        missing = policy()
        missing.pollen_source_policy = type(missing.pollen_source_policy)(channels=[])
        hidden = pollen.exact_entry(session, settings=missing, user_id="owner", subject_id=subject, entry_id=item["id"], now=at)
        assert hidden["entry"]["source_withheld"]
        assert hidden["entry"]["current"]["value"] is None and hidden["entry"]["previous"] is None
        assert not hidden["entry"]["raw_export_available"]


def test_http_sections_are_available_but_unavailable_is_not_empty_success(centre):
    client, _, settings, _ = centre
    enabled(settings)
    for domain in notifications.DOMAINS[:-1]:
        response = client.get("/api/monitoring-centre/notifications", params={"domain": domain})
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "available" and response.json()["items"] == []
        assert "no-store" in response.headers["cache-control"]
    settings.air_watch_enabled = False
    response = client.get("/api/monitoring-centre/notifications?domain=air")
    assert response.json()["state"] == "unavailable"
    for query in ("domain=customs", "domain=river&cursor=broken", "domain=legal"):
        denied = client.get("/api/monitoring-centre/notifications?" + query)
        assert denied.status_code == 422 and "no-store" in denied.headers["cache-control"]
