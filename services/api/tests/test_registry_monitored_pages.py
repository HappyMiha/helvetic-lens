"""The monitoring list reads bounded scalar pages, including legacy-only watches."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.config import Config
from conftest import add_law, import_old
from sqlalchemy import event as sa_event
from sqlalchemy import insert, inspect, select
from sqlalchemy.orm import Session
from test_registry_event_pages import seed

from alembic import command
from helvetic_lens.models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Organization,
    RegulatoryDate,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RegulatoryExpression,
    RegulatoryWork,
    Version,
)
from helvetic_lens.registry import RegistryFilters, RegistryReader


def seed_watches(service, count=231, *, mapped=True):
    event_ids, works, stamp = seed(service, 231) if mapped else ([], [], datetime(2026, 9, 6, 9, tzinfo=UTC))
    watch_ids = [f"97000000-0000-0000-0000-{i:012d}" for i in range(count)]
    law_ids = [f"98000000-0000-0000-0000-{i:012d}" for i in range(count)]
    with service.db.session() as session:
        session.execute(
            insert(Law),
            [
                dict(
                    id=id_,
                    canonical_identity=id_,
                    name="Law",
                    url=f"https://example.test/{i}",
                    provider="native",
                )
                for i, id_ in enumerate(law_ids)
            ],
        )
        session.execute(
            insert(DocumentWatch),
            [
                dict(
                    id=id_,
                    law_id=law_ids[i],
                    organization_id=service.organization_id,
                    display_name="RÉVISION 100% _" if i < 2 else "Ordinary monitoring",
                    active=bool(i % 2),
                    created_at=stamp - timedelta(days=2),
                    last_checked=stamp - timedelta(days=1),
                )
                for i, id_ in enumerate(watch_ids)
            ],
        )
        if mapped:
            session.execute(
                insert(LegacyDocumentMapping),
                [dict(law_id=id_, work_id=works[0], mapping_status="provisional") for id_ in law_ids],
            )
            session.add(
                RegulatoryDate(
                    entity_type="work",
                    entity_id=works[0],
                    kind="published_at",
                    date_value="2026-08-01",
                    precision="day",
                    provenance="official_metadata",
                    evidence_json={"large": "x" * 4000},
                )
            )
        session.commit()
    return watch_ids, law_ids, event_ids, works, stamp


def test_monitored_keysets_batch_details_without_hydrating_saved_bodies(harness):
    client, _, service, model = harness
    ids, _, events, _, _ = seed_watches(service)
    loaded, queries = [], []

    def load(_session, value):
        if isinstance(
            value,
            (
                DocumentWatch,
                Law,
                Comparison,
                Version,
                RegulatoryWork,
                RegulatoryEvent,
                RegulatoryExpression,
                RegulatoryEventUserState,
            ),
        ):
            loaded.append(type(value).__name__)

    def sql(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    sa_event.listen(Session, "loaded_as_persistent", load)
    sa_event.listen(service.db.engine, "before_cursor_execute", sql)
    try:
        seen, cursor = [], ""
        for size in (100, 100, 31):
            response = client.get(
                "/api/registry", params={"view": "monitored", "limit": 100, "cursor": cursor}
            )
            assert response.status_code == 200, response.text
            page = response.json()
            assert page["count"] == len(page["items"]) == size
            seen.extend(row["id"] for row in page["items"])
            assert all(row["event_id"] == events[-1] and row["languages"] == ["fr"] for row in page["items"])
            assert all(
                row["official_dates"]["published_at"][0]["value"] == "2026-08-01" for row in page["items"]
            )
            assert all(
                "active" not in row and "watch_id" not in row and "law_url" not in row
                for row in page["items"]
            )
            cursor = page["next_cursor"]
        assert seen == ["watch:" + id_ for id_ in reversed(ids)] and cursor is None
        assert loaded == []
        assert all(
            "evidence_json" not in q and "metadata_json" not in q and "comparisons.diff" not in q
            for q in queries
        )
        candidates = [q for q in queries if "document_watches.id AS watch_id" in q]
        assert len(candidates) == 5 and all("LIMIT" in q for q in candidates)
        assert len([q for q in queries if "regulatory_dates.entity_id" in q]) == 3
        assert len([q for q in queries if "row_number() OVER (PARTITION BY comparisons.law_id" in q]) == 3
        assert model.calls == []
    finally:
        sa_event.remove(Session, "loaded_as_persistent", load)
        sa_event.remove(service.db.engine, "before_cursor_execute", sql)


def test_monitored_sparse_literal_search_and_legacy_defaults(harness, monkeypatch):
    client, _, service, _ = harness
    ids, _, _, _, stamp = seed_watches(service, mapped=False)
    expanded = []
    original = RegistryReader._monitored_details

    def details(reader, session, rows):
        expanded.extend(row["id"] for row in rows)
        return original(reader, session, rows)

    monkeypatch.setattr(RegistryReader, "_monitored_details", details)
    filters = dict(
        view="monitored",
        limit=1,
        q="revision 100% _",
        language="und",
        health="unknown",
        kind="unclassified_document",
        lifecycle="unknown",
        impact="unknown",
        read="unread",
        watched="watched",
    )
    first = client.get("/api/registry", params=filters).json()
    assert first["items"][0]["id"] == "watch:" + ids[1]
    assert first["items"][0]["event_id"] is None and first["items"][0]["event_type"] == "monitoring_started"
    assert first["items"][0]["detected_at"] == (stamp - timedelta(days=1)).isoformat()
    assert expanded == ["watch:" + ids[1]]
    second = client.get("/api/registry", params={**filters, "cursor": first["next_cursor"]}).json()
    assert second["items"][0]["id"] == "watch:" + ids[0] and second["next_cursor"] is None
    assert not second["items"][0]["linked_laws"][0]["active"]
    assert client.get("/api/registry", params={"view": "monitored", "language": "fr"}).json()["items"] == []
    assert (
        client.get("/api/registry", params={"view": "monitored", "watched": "unwatched"}).json()["items"]
        == []
    )
    assert (
        client.get("/api/registry", params={"view": "monitored", "q": "100% not wildcard"}).json()["items"]
        == []
    )


def test_monitored_current_user_read_state_ignores_older_event_and_foreign_principal(harness):
    _, _, service, _ = harness
    _, _, events, _, _ = seed_watches(service, 1)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign read", slug="monitored-foreign-read")
        session.add(foreign)
        session.flush()
        session.add_all(
            [
                RegulatoryEventUserState(
                    organization_id=service.organization_id,
                    event_id=events[-2],
                    principal_key="user:alice",
                    state="read",
                ),
                RegulatoryEventUserState(
                    organization_id=foreign.id, event_id=events[-1], principal_key="user:alice", state="read"
                ),
                RegulatoryEventUserState(
                    organization_id=service.organization_id,
                    event_id=events[-1],
                    principal_key="user:bob",
                    state="read",
                ),
            ]
        )
        session.commit()
        assert (
            RegistryReader(service.organization_id, "alice").page(session, RegistryFilters(read="read"))[
                "items"
            ]
            == []
        )
        assert (
            len(
                RegistryReader(service.organization_id, "alice").page(
                    session, RegistryFilters(read="unread")
                )["items"]
            )
            == 1
        )
        assert (
            len(
                RegistryReader(service.organization_id, "bob").page(session, RegistryFilters(read="read"))[
                    "items"
                ]
            )
            == 1
        )


def test_monitored_privileged_scope_never_borrows_foreign_law_mapping_or_work(harness):
    _, _, service, _ = harness
    ids, laws, _, _, _ = seed_watches(service, 5)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign owner", slug="monitored-foreign-owner")
        session.add(foreign)
        session.flush()
        session.get(Law, laws[0]).owner_organization_id = foreign.id
        session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == laws[1])
        ).owner_organization_id = foreign.id
        work = RegulatoryWork(
            owner_organization_id=foreign.id,
            authority="secret",
            kind="act",
            canonical_key="private-monitored",
            title="Private",
        )
        session.add(work)
        session.flush()
        session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == laws[2])
        ).work_id = work.id
        session.get(DocumentWatch, ids[3]).organization_id = foreign.id
        session.commit()
        rows = RegistryReader(service.organization_id).page(session, RegistryFilters())["items"]
        assert {row["id"] for row in rows} == {"watch:" + ids[i] for i in (1, 2, 4)}
        for row in rows:
            if row["id"] != "watch:" + ids[4]:
                assert row["work_id"] is None and row["event_id"] is None
                assert (
                    row["authority"] == "native"
                    and row["languages"] == ["und"]
                    and row["official_dates"] == {}
                )


def test_monitored_dates_use_zurich_and_creation_fallback(harness):
    client, _, service, _ = harness
    ids, _, _, _, _ = seed_watches(service, 4, mapped=False)
    start = datetime(2026, 10, 24, 22, tzinfo=UTC)
    end = datetime(2026, 10, 25, 23, tzinfo=UTC)  # 25-hour day.
    with service.db.session() as session:
        for id_, stamp in zip(
            ids, [start - timedelta(microseconds=1), start, end - timedelta(microseconds=1), end]
        ):
            watch = session.get(DocumentWatch, id_)
            watch.last_checked = None
            watch.created_at = stamp
        session.commit()
    response = client.get(
        "/api/registry", params={"view": "monitored", "start": "2026-10-25", "end": "2026-10-25"}
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == ["watch:" + ids[2], "watch:" + ids[1]]


def test_monitored_comparison_links_choose_latest_visible_scalar_id(harness):
    client, _, service, model = harness
    law = add_law(client)
    import_old(client, law["id"])
    with service.db.session(include_all_organizations=True) as session:
        versions = list(session.scalars(select(Version.id).where(Version.law_id == law["id"])))
        stamp = datetime(2026, 9, 6, 9, tzinfo=UTC)
        for i in (1, 2):
            session.add(
                Comparison(
                    id=f"99000000-0000-0000-0000-{i:012d}",
                    law_id=law["id"],
                    old_version_id=versions[0],
                    new_version_id=versions[1],
                    mode=f"visible-test-{i}",
                    diff={"large": "x" * 100000},
                    created_at=stamp,
                )
            )
        session.flush()
        original = session.get(Comparison, "99000000-0000-0000-0000-000000000002")
        original_id = original.id
        foreign = Organization(name="Foreign comparison", slug="monitored-foreign-comparison")
        session.add(foreign)
        session.flush()
        session.add(
            Comparison(
                owner_organization_id=foreign.id,
                law_id=law["id"],
                old_version_id=original.old_version_id,
                new_version_id=original.new_version_id,
                mode="foreign-test",
                diff={"large": "x" * 100000},
                created_at=original.created_at + timedelta(days=1),
            )
        )
        session.commit()
        rows = RegistryReader(service.organization_id).page(session, RegistryFilters())["items"]
        assert rows[0]["comparison_url"] == "/compare/" + original_id
        assert rows[0]["evidence_url"] == "/evidence/" + session.get(Law, law["id"]).current_version_id
        assert model.calls == []


def test_monitored_latest_event_index_roundtrip_preserves_events(harness):
    service = harness[2]
    _, _, events, _, _ = seed_watches(service, 2)
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "a183fc729650")
        assert "ix_regulatory_event_work_latest" not in {
            i["name"] for i in inspect(connection).get_indexes("regulatory_events")
        }
        command.upgrade(config, "head")
        assert any(
            i["name"] == "ix_regulatory_event_work_latest"
            and i["column_names"] == ["work_id", "detected_at", "id"]
            for i in inspect(connection).get_indexes("regulatory_events")
        )
        assert set(connection.scalars(select(RegulatoryEvent.id))) == set(events)
