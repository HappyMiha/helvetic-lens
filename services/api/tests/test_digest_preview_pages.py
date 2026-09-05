"""Interactive digest reads bound sparse work without scheduling mail or inference."""

import base64
import json
from datetime import timedelta

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_digest_periods import recipient, seed_events

from helvetic_lens import digests
from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import (
    DigestDelivery,
    DigestPreference,
    Job,
    Organization,
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RelationCandidate,
    new_id,
)


def test_http_preview_bounds_sparse_pages_and_save_without_mail_or_inference(harness, monkeypatch):
    client, _, service, model = harness
    registered = client.post(
        "/api/auth/register",
        json={
            "email": "preview@example.invalid",
            "password": "test only long password",
            "name": "Preview tester",
            "organization_name": "Preview test organization",
        },
    )
    assert registered.status_code == 201, registered.text
    identity = client.get("/api/auth/session").json()
    org = identity["organization"]["id"]
    client.headers["X-CSRF-Token"] = client.cookies.get(CSRF_COOKIE)
    stamp = utcnow() - timedelta(minutes=1)
    ids = [f"86000000-0000-0000-0000-{i:012d}" for i in range(121)]
    with service.db.organization_context(org):
        seed_events(
            harness,
            [
                {"id": id_, "detected_at": stamp, "impact": "high" if i < 21 else "low"}
                for i, id_ in enumerate(ids)
            ],
        )
        with service.db.session() as session:
            jobs_before = session.scalar(select(func.count()).select_from(Job))

    def forbid(*args, **kwargs):
        raise AssertionError("A preview must never deliver mail")

    monkeypatch.setattr(AuthMailer, "send_message", forbid)
    loaded = []

    def record(_session, row):
        if isinstance(row, RegulatoryEvent):
            loaded.append(row.id)

    event.listen(Session, "loaded_as_persistent", record)
    try:
        response = client.put(
            "/api/digests/preferences?preview_page=true",
            json={
                "enabled": False,
                "frequency": "daily",
                "severities": ["high"],
                "sources": [],
            },
        )
        assert response.status_code == 200, response.text
        first = response.json()["preview"]
        assert first["events"] == [] and first["has_more"] and first["scanned_event_count"] == 50
        assert len(loaded) == 50 and set(loaded) == set(ids[71:])
        assert first["counts_scope"] == "page" and not first["truncated"]
        cursor, matched = first["next_cursor"], []
        for count in (50, 21):
            loaded.clear()
            response = client.get("/api/digests", params={"preview_page": True, "cursor": cursor})
            assert response.status_code == 200, response.text
            page = response.json()["preview"]
            assert page["period_start"] == first["period_start"] and page["period_end"] == first["period_end"]
            assert page["scanned_event_count"] == count and len(loaded) == count
            matched.extend(item["event_id"] for item in page["events"])
            cursor = page["next_cursor"]
        assert matched == list(reversed(ids[:21])) and cursor is None and not page["has_more"]
        back = client.get(
            "/api/digests", params={"preview_page": True, "cursor": first["current_cursor"]}
        ).json()["preview"]
        assert back == first  # Back pins the first period rather than starting a new one.
        legacy = client.get("/api/digests").json()["preview"]
        assert [item["event_id"] for item in legacy["events"]] == matched and "counts_scope" not in legacy
        with service.db.organization_context(org), service.db.session() as session:
            assert session.scalar(select(func.count()).select_from(Job)) == jobs_before
            assert session.scalar(select(func.count()).select_from(DigestDelivery)) == 0
            assert session.scalar(select(func.count()).select_from(RegulatoryEventUserState)) == 0
        assert model.calls == []
    finally:
        event.remove(Session, "loaded_as_persistent", record)


def test_preview_cursor_binds_reader_organization_and_saved_filters(harness):
    _, _, service, _ = harness
    user = recipient(service)
    first = service.digest_overview(user, preview_page=True)["preview"]["current_cursor"]
    other = recipient(service, "other-preview@example.invalid")
    with pytest.raises(DomainError) as error:
        service.digest_overview(other, preview_page=True, cursor=first)
    assert error.value.code == "invalid_digest_cursor"
    for change in (
        {"enabled": True},
        {"frequency": "daily"},
        {"severities": ["high"]},
        {"sources": ["fedlex"]},
    ):
        preference = DigestPreference(enabled=False, frequency="weekly", sources=[], severities=[])
        for key, value in change.items():
            setattr(preference, key, value)
        with service.db.session() as session, pytest.raises(DomainError, match="Restart"):
            digests.preview_page(
                session, ImpactInboxReader(service.organization_id, user, settings=service.settings, prompts=service.prompt_settings), preference, cursor=first
            )
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign preview", slug="foreign-preview")
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    with service.db.organization_context(foreign_id):
        with pytest.raises(DomainError, match="Restart"):
            service.digest_overview(user, preview_page=True, cursor=first)
        assert service.digest_overview(user, preview_page=True)["preview"]["events"] == []


@pytest.mark.parametrize(
    "bad",
    [
        "!not-base64",
        "A" * 2049,
        "[]",
        "null",
        "{}",
        "null-time",
        "naive-time",
        "underflow",
        "outside-period",
        "oversized-id",
    ],
)
def test_preview_rejects_invalid_positions_without_hydrating_events(harness, monkeypatch, bad):
    client, _, service, _ = harness
    user = recipient(service)
    token = service.digest_overview(user, preview_page=True)["preview"]["current_cursor"]
    data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    if bad in ("[]", "null", "{}"):
        token = base64.urlsafe_b64encode(bad.encode()).decode()
    elif bad in ("!not-base64", "A" * 2049):
        token = bad
    else:
        if bad == "null-time":
            data["period_end"] = None
        elif bad == "naive-time":
            data["period_end"] = "2026-09-05T10:00:00"
        elif bad == "underflow":
            data["period_end"] = "0001-01-01T00:00:00+00:00"
        else:
            data["after"] = {
                "id": "x" * (37 if bad == "oversized-id" else 1),
                "detected_at": data["period_end"],
            }
        token = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

    def forbid(*args, **kwargs):
        raise AssertionError("Invalid cursor reached event hydration")

    monkeypatch.setattr(ImpactInboxReader, "event_page", forbid)
    with pytest.raises(DomainError) as error:
        service.digest_overview(user, preview_page=True, cursor=token)
    assert error.value.code == "invalid_digest_cursor"
    assert client.get("/api/digests?preview_page=true").status_code == 401


def test_preview_pins_period_and_excludes_late_admissions_but_refresh_sees_them(harness, monkeypatch):
    _, _, service, _ = harness
    stamp = utcnow() - timedelta(minutes=1)
    original, late = new_id(), new_id()
    seed_events(harness, [{"id": original, "detected_at": stamp}, {"id": late, "detected_at": stamp}])
    user = recipient(service)
    end = utcnow()
    with service.db.session() as session:
        delivery = session.scalar(
            select(OrganizationRelationCandidate)
            .join(RelationCandidate)
            .where(RelationCandidate.event_id == late)
        )
        delivery.created_at = end + timedelta(seconds=1)
        session.commit()
    monkeypatch.setattr(digests, "utcnow", lambda: end)
    first = service.digest_overview(user, preview_page=True)["preview"]
    assert [item["event_id"] for item in first["events"]] == [original]
    monkeypatch.setattr(digests, "utcnow", lambda: end + timedelta(seconds=2))
    again = service.digest_overview(user, preview_page=True, cursor=first["current_cursor"])["preview"]
    assert again == first
    fresh = service.digest_overview(user, preview_page=True)["preview"]
    assert {item["event_id"] for item in fresh["events"]} == {original, late}
    service.set_impact_inbox_state(original, "muted", user)
    assert (
        service.digest_overview(user, preview_page=True, cursor=first["current_cursor"])["preview"]["events"]
        == []
    )
