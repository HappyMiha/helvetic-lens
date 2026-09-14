"""Real migrated storage and native GET→private tracking; no real source grants."""

import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from test_aste_parser import END, NOW, detail, listing, status
from test_auction_sources import grant
from test_auction_workflow import action, create, sync, view
from test_tender_repository import db as _db
from test_tender_repository import template as _template

from helvetic_lens import aste_collection as collection
from helvetic_lens import auction_sources as sources
from helvetic_lens import auction_workflow as workflow
from helvetic_lens.aste_collector import collect
from helvetic_lens.aste_models import AsteCollector, AsteItem, AsteListingEvidence
from helvetic_lens.aste_parser import ORIGIN, SOURCE_KEY
from helvetic_lens.auction_source_models import AuctionSourceReceipt, AuctionSourceRecordRevision
from helvetic_lens.config import DomainError, Settings

db, template = _db, _template
DOCUMENT_PATH = "/uploads/146/" + "a" * 32 + ".pdf"


def permission(db, **changes):
    values = dict(source_key=SOURCE_KEY, endpoint=ORIGIN + "/", categories=("bicycles",),
        accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=2),
        private_decisions_allowed=True, notifications_allowed=True,
        min_poll_seconds=60, max_age_seconds=600, raw_retention_seconds=1200,
        native_access={"adapter_version": "aste-public-v1", "request_interval_seconds": 1,
            "document_download_allowed": True, "category_mapping": {"30": {"label": "Biciclette", "category": "bicycles"}}})
    return grant(db, **{**values, **changes})


class Publisher:
    def __init__(self):
        self.now, self.bid, self.count, self.pdf = NOW, 8500, 6, b"%PDF-1.7 synthetic conditions v1"
        self.calls, self.remove, self.error = [], False, None
        self.end = END

    def request(self, request):
        self.calls.append(str(request.url))
        if self.error:
            return httpx.Response(self.error, headers={"retry-after": "600"})
        path = request.url.path
        if path in ("/it/", "/it/preview"):
            body = listing(ids=() if self.remove else ("185",), active="data-active-filter" if request.url.params.get("category[]") else "")
            kind = "text/html"
        elif path == "/it/auction/185":
            links = f'<div class="pdf-files-container"><a class="auction-detail-media-link" href="{DOCUMENT_PATH}?2.35"><span class="document-title">Condizioni d&#39;asta</span></a></div>'
            body, kind = detail(documents=links), "text/html"
        elif path == "/it/api/auction/auction-status/185":
            data = json.loads(status(numberBids=self.count, currentPrice=self.bid, highestBidPrice=f"CHF {self.bid:.2f}"))
            data["time"]["server_time"]["timestamp"] = int(self.now.timestamp())
            data["time"]["auction_end_date"].update(timestamp=int(self.end.timestamp()),
                date=self.end.astimezone(collection.parser.ZONE).strftime("%Y-%m-%d %H:%M:%S"))
            body, kind = json.dumps(data).encode(), "application/json"
        elif path == DOCUMENT_PATH:
            body, kind = self.pdf, "application/pdf"
        else:
            raise AssertionError("Unexpected native request: " + str(request.url))
        return httpx.Response(200, headers={"content-type": kind}, stream=httpx.ByteStream(body))


def settings(identifier):
    return Settings(_env_file=None, auction_watch_enabled=True, aste_source_enabled=True, aste_source_permission_id=identifier)


def run_to_record(db, identifier, publisher, *, sequence=1):
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        for _ in range(40):
            result = collect(db, settings(identifier), client=client, now=publisher.now)
            assert result["state"] != "unavailable", result
            with db.session() as session:
                count = session.scalar(select(func.count()).select_from(AuctionSourceReceipt))
                if count >= sequence:
                    return
            publisher.now += timedelta(seconds=1)
    raise AssertionError("No native record admitted")


def test_native_pdf_category_price_and_end_changes_reopen_private_review(db):
    identifier, publisher = permission(db), Publisher()
    run_to_record(db, identifier, publisher)
    with db.session() as session:
        record = sources.read_current(session, SOURCE_KEY, now=publisher.now)["items"][0]["facts"]
        assert record.category == "bicycles" and record.price("current_bid").amount_minor == 850000
        assert record.documents.state == "complete" and record.documents.items[0].sha256
        assert record.conditions_sha256 == record.documents.items[0].sha256
    monitor = create(db, categories=["bicycles"])
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=publisher.now)
        workflow.refresh(session, "owner", monitor, now=publisher.now)
        session.commit()
    first = action(db, monitor, now=publisher.now, decision="inspect")
    publisher.bid, publisher.pdf, publisher.end = 12700, b"%PDF-1.7 synthetic revised conditions", END + timedelta(hours=1)
    publisher.now += timedelta(seconds=61)
    run_to_record(db, identifier, publisher, sequence=2)
    sync(db, monitor, now=publisher.now)
    second = view(db, monitor, now=publisher.now)
    assert second["needs_review"] and second["decision"] == "inspect"
    assert second["material_sequence"] > first["material_sequence"]
    assert second["facts"]["prices"][1]["amount_minor"] == 1270000
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                workflow.list_items(session, user, monitor, now=publisher.now)
        from helvetic_lens.auction_workflow_models import AuctionItemEvent
        events = list(session.scalars(select(AuctionItemEvent)))
        codes = {code for event in events for code in event.change_codes}
        assert {"price_above_limit", "deadline_changed", "document_changed", "conditions_changed"}.issubset(codes)


def test_unknown_disappearance_still_rechecks_known_identity(db):
    identifier, publisher = permission(db), Publisher()
    run_to_record(db, identifier, publisher)
    publisher.remove, publisher.now = True, publisher.now + timedelta(seconds=61)
    publisher.bid = 9000
    run_to_record(db, identifier, publisher, sequence=2)
    with db.session() as session:
        record = sources.read_current(session, SOURCE_KEY, now=publisher.now)["items"][0]["facts"]
        assert record.status == "open" and record.price("current_bid").amount_minor == 900000
        assert session.scalar(select(func.count()).select_from(AsteItem)) == 1


def test_claim_replay_rate_and_revocation_prevent_http_and_admission(db):
    identifier = permission(db)
    with db.session() as session:
        first = collection.claim(session, identifier, now=NOW)
        session.commit()
    with db.session() as session:
        assert collection.claim(session, identifier, now=NOW + timedelta(seconds=2)) is None
        collection.succeed(session, first, listing(), now=NOW)
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError):
            collection.succeed(session, first, listing(), now=NOW)
        assert collection.claim(session, identifier, now=NOW) is None
    with db.session() as session:
        sources.revoke_permission(session, identifier, now=NOW)
        session.commit()
    publisher = Publisher()
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        assert collect(db, settings(identifier), client=client, now=NOW)["state"] == "unavailable"
    assert not publisher.calls


def test_provider_backoff_survives_restart_and_has_no_early_retry(db):
    identifier, publisher = permission(db), Publisher()
    publisher.error = 429
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        assert collect(db, settings(identifier), client=client, now=NOW)["reason"] == "aste_http_429"
        assert collect(db, settings(identifier), client=client, now=NOW + timedelta(seconds=599))["state"] == "waiting"
    assert len(publisher.calls) == 1
    with db.session() as session:
        state = session.get(AsteCollector, SOURCE_KEY)
        assert state.lease_token is None and state.last_error == "aste_http_429"


def test_expiry_purges_payloads_without_deleting_private_source_history(db):
    identifier, publisher = permission(db), Publisher()
    run_to_record(db, identifier, publisher)
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(AsteListingEvidence)) > 0
        sources.revoke_permission(session, identifier, now=publisher.now)
        session.commit()
    with db.session() as session:
        result = collection.cleanup(session, now=publisher.now)
        session.commit()
        assert result["listing_proofs"] > 0
        assert session.scalar(select(func.count()).select_from(AuctionSourceRecordRevision)) > 0
        assert session.get(AsteItem, "185").category_proofs == {}
        assert collection.cleanup(session, now=publisher.now) == {"item_payloads": 0, "listing_payloads": 0, "listing_proofs": 0}


def test_expired_lease_restarts_without_accepting_late_worker(db):
    identifier = permission(db)
    with db.session() as session:
        first = collection.claim(session, identifier, now=NOW)
        session.commit()
    db.engine.dispose()
    later = NOW + timedelta(seconds=121)
    with db.session() as session:
        replacement = collection.claim(session, identifier, now=later)
        session.commit()
    assert replacement["url"] == first["url"] and replacement["token"] != first["token"]
    with db.session() as session:
        with pytest.raises(DomainError):
            collection.succeed(session, first, listing(), now=later)
    with db.session() as session:
        collection.succeed(session, replacement, listing(), now=later)
        session.commit()
        assert session.scalar(select(func.count()).select_from(AsteItem)) == 1
        assert session.scalar(select(func.count()).select_from(AsteListingEvidence)) == 1


def test_permission_replacement_discards_staged_data_and_rejects_old_ticket(db):
    identifier, publisher = permission(db), Publisher()
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        for _ in range(2):  # Listing then detail are committed before restart.
            collect(db, settings(identifier), client=client, now=publisher.now)
            publisher.now += timedelta(seconds=1)
    with db.session() as session:
        old = collection.claim(session, identifier, now=publisher.now)
        session.commit()
        assert session.get(AsteItem, "185").detail_payload is not None
    replacement = permission(db, generation=1)
    later = publisher.now + timedelta(seconds=121)
    with db.session() as session:
        ticket = collection.claim(session, replacement, now=later)
        session.commit()
        item = session.get(AsteItem, "185")
        assert item.detail_payload is None and not item.documents and not item.category_proofs
        assert item.permission_id == replacement
    with db.session() as session:
        with pytest.raises(DomainError):
            collection.succeed(session, old, listing(), now=later)
        assert session.scalar(select(func.count()).select_from(AuctionSourceReceipt)) == 0
    assert ticket["permission_id"] == replacement


@pytest.mark.parametrize("failure", ["malformed", "capacity"])
def test_listing_failure_rolls_back_discovery_and_keeps_retry_checkpoint(db, monkeypatch, failure):
    identifier, publisher = permission(db), Publisher()
    if failure == "capacity":
        monkeypatch.setattr(collection, "MAX_ITEMS", 0)
    handler = publisher.request if failure == "capacity" else lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(b"<html>No official listing</html>"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert collect(db, settings(identifier), client=client, now=NOW)["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(AsteItem)) == 0
        assert session.scalar(select(func.count()).select_from(AsteListingEvidence)) == 0
        row = session.get(AsteCollector, SOURCE_KEY)
        assert row.listing_queue[0] == collection.parser.listing_url() and row.lease_token is None


def test_invalid_document_does_not_publish_partial_record(db):
    identifier, publisher = permission(db), Publisher()
    publisher.pdf = b"<html>Sign in</html>"
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        for _ in range(15):
            result = collect(db, settings(identifier), client=client, now=publisher.now)
            if result["state"] == "unavailable":
                break
            publisher.now += timedelta(seconds=1)
    assert result["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(AuctionSourceReceipt)) == 0
        item = session.get(AsteItem, "185")
        assert item.last_error and item.detail_payload is None and item.stage == "detail"


@pytest.mark.parametrize("problem", ["stale", "tampered", "wrong_label"])
def test_category_requires_fresh_unaltered_matching_publisher_proof(db, problem):
    identifier, publisher = permission(db), Publisher()
    run_to_record(db, identifier, publisher)
    with db.session() as session:
        policy, _ = collection.scope(session, identifier, now=publisher.now)
        item = session.get(AsteItem, "185")
        assert collection._category(session, policy, item, publisher.now)[0] == "bicycles"
        proof = session.get(AsteListingEvidence, item.category_proofs["30"])
        if problem == "tampered":
            proof.raw_payload = b"altered"
        if problem == "wrong_label":
            policy = policy.model_copy(update={"native_access": policy.native_access.model_copy(update={
                "category_mapping": {"30": policy.native_access.category_mapping["30"].model_copy(update={"label": "Other"})}})})
        at = publisher.now + timedelta(seconds=601) if problem == "stale" else publisher.now
        assert collection._category(session, policy, item, at)[0] is None


def test_legacy_permission_is_unchanged_and_cannot_trigger_native_requests(db):
    from test_auction_sources import policy
    original = policy()
    encoded = original.model_dump(mode="json")
    assert "native_access" not in encoded
    assert sources.AuctionSourcePolicy.model_validate_json(json.dumps(encoded)).model_dump(mode="json") == encoded
    identifier, publisher = permission(db, native_access=None), Publisher()
    with httpx.Client(transport=httpx.MockTransport(publisher.request)) as client:
        assert collect(db, settings(identifier), client=client, now=NOW)["reason"] == "aste_native_access_required"
    assert publisher.calls == []


def test_native_migration_preserves_private_decisions(db):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    from alembic import command
    from helvetic_lens.auction_workflow_models import AuctionDecision
    from helvetic_lens.db import Base
    identifier, publisher = permission(db), Publisher()
    run_to_record(db, identifier, publisher)
    monitor = create(db, categories=["bicycles"])
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=publisher.now)
        workflow.refresh(session, "owner", monitor, now=publisher.now)
        session.commit()
    action(db, monitor, now=publisher.now, decision="inspect")
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("aste_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "e7c4a56806e9")
        assert connection.scalar(select(func.count()).select_from(AuctionDecision)) == 1
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
        assert connection.scalar(select(func.count()).select_from(AuctionDecision)) == 1


def test_native_deadline_changes_replace_reminders_and_feed_remains_owner_private(db):
    from test_auction_rules import profile

    from helvetic_lens import auction_reminders as reminders
    from helvetic_lens import auction_today as today
    from helvetic_lens.aste_collector import status as source_status
    from helvetic_lens.auction_workflow_models import AuctionReminder
    identifier, publisher = permission(db), Publisher()
    publisher.end = NOW + timedelta(hours=20)
    run_to_record(db, identifier, publisher)
    monitor = create(db, categories=["bicycles"], notify={**profile().notify.model_dump(), "ending_soon_hours": 24})
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=publisher.now)
        workflow.refresh(session, "owner", monitor, now=publisher.now)
        session.commit()
    action(db, monitor, now=publisher.now, following=True)
    assert reminders.activate_due(db, settings(identifier), now=publisher.now)["ready"] == 1
    with db.session() as session:
        initial = reminders.page(session, "owner", now=publisher.now)["items"][0]
        assert initial["eligible"]
        assert today.page(session, settings(identifier), "owner", now=publisher.now)["items"]
        assert today.page(session, settings(identifier), "peer", now=publisher.now)["items"] == []
        state = source_status(session, settings(identifier), now=publisher.now)
        assert state["state"] == "configured" and not state["coverage_verified"]
        assert state["collection"]["known_items"] == 1 and state["collection"]["last_record_at"]
    publisher.end += timedelta(hours=1)
    publisher.now += timedelta(seconds=61)
    run_to_record(db, identifier, publisher, sequence=2)
    sync(db, monitor, now=publisher.now)
    assert reminders.activate_due(db, settings(identifier), now=publisher.now)["ready"] == 1
    with db.session() as session:
        changed = reminders.page(session, "owner", now=publisher.now)["items"][0]
        assert changed["id"] != initial["id"] and changed["eligible"]
        assert session.get(AuctionReminder, initial["id"]).state == "invalidated"
        sources.revoke_permission(session, identifier, now=publisher.now)
        session.commit()
    with db.session() as session:
        assert reminders.page(session, "owner", now=publisher.now)["items"] == []
        assert today.page(session, settings(identifier), "owner", now=publisher.now)["items"] == []
