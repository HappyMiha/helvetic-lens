"""Registry event pages must not hydrate the entire saved corpus."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.config import Config
from conftest import add_law
from sqlalchemy import event as sa_event
from sqlalchemy import insert, inspect, select
from sqlalchemy.orm import Session

from alembic import command
from helvetic_lens.models import (
    DocumentWatch,
    LegacyDocumentMapping,
    Organization,
    RegulatoryDate,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    new_id,
)
from helvetic_lens.registry import RegistryFilters, RegistryReader


def seed(service, count=231, *, individual=False):
    stamp = datetime(2026, 9, 6, 9, tzinfo=UTC)
    ids = [f"96000000-0000-0000-0000-{i:012d}" for i in range(count)]
    work_ids = [new_id() for _ in range(count if individual else 1)]
    with service.db.session() as session:
        session.execute(
            insert(RegulatoryWork),
            [
                dict(
                    id=work_id,
                    authority="registry-qa",
                    kind="act",
                    canonical_key=work_id,
                    title=("RÉVISION 100% _" if i < 2 and individual else "Ordinary regulation"),
                    metadata_json={"large": "x" * 4000},
                )
                for i, work_id in enumerate(work_ids)
            ],
        )
        session.execute(
            insert(RegulatoryExpression),
            [
                dict(
                    work_id=work_id,
                    language="fr",
                    expression_key=work_id,
                    metadata_json={"large": "x" * 4000},
                )
                for work_id in work_ids
            ],
        )
        session.execute(
            insert(RegulatoryEvent),
            [
                dict(
                    id=id_,
                    work_id=work_ids[i] if individual else work_ids[0],
                    authority="registry-qa",
                    event_type="new_version",
                    dedupe_key=id_,
                    detected_at=stamp,
                    connector="registry-qa",
                    connector_health="healthy",
                    analysis_state="pending",
                    impact="low",
                    provenance_method="official_metadata",
                    evidence_json={"large": "x" * 4000},
                )
                for i, id_ in enumerate(ids)
            ],
        )
        session.commit()
    return ids, work_ids, stamp


def test_equal_time_registry_pages_do_not_hydrate_event_or_work_payloads(harness):
    client, _, service, model = harness
    ids, _, _ = seed(service, 231)
    loaded, queries = [], []

    def record(_session, row):
        if isinstance(row, (RegulatoryEvent, RegulatoryWork, RegulatoryExpression, RegulatoryEventUserState)):
            loaded.append(type(row).__name__)

    def sql(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append((statement, parameters))

    sa_event.listen(Session, "loaded_as_persistent", record)
    sa_event.listen(service.db.engine, "before_cursor_execute", sql)
    try:
        seen, cursor = [], ""
        for expected in (100, 100, 31):
            response = client.get(
                "/api/registry",
                params={"view": "events", "limit": 100, "cursor": cursor, "authority": "registry-qa"},
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["count"] == len(result["items"]) == expected
            seen.extend(row["event_id"] for row in result["items"])
            assert all(row["languages"] == ["fr"] and not row["watched"] for row in result["items"])
            cursor = result["next_cursor"]
        assert seen == list(reversed(ids)) and cursor is None
        assert loaded == []
        assert all("evidence_json" not in sql and "metadata_json" not in sql for sql, _ in queries)
        candidates = [sql for sql, _ in queries if "regulatory_events.id AS event_id" in sql]
        assert len(candidates) == 5  # two bounded selects for 100+lookahead, then the final 31.
        assert all(
            "LIMIT" in sql and "ORDER BY regulatory_events.detected_at DESC, regulatory_events.id DESC" in sql
            for sql in candidates
        )
        assert model.calls == []
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
        sa_event.remove(service.db.engine, "before_cursor_execute", sql)


def test_sparse_unicode_search_crosses_batches_and_only_expands_visible_details(harness, monkeypatch):
    client, _, service, _ = harness
    ids, _, _ = seed(service, 231, individual=True)
    expanded = []
    original = RegistryReader._event_details

    def details(reader, session, rows):
        expanded.extend(row["event_id"] for row in rows)
        return original(reader, session, rows)

    monkeypatch.setattr(RegistryReader, "_event_details", details)
    response = client.get(
        "/api/registry", params={"view": "events", "limit": 1, "q": "revision 100% _", "language": "fr"}
    )
    assert response.status_code == 200, response.text
    first = response.json()
    assert [row["event_id"] for row in first["items"]] == [ids[1]]
    assert expanded == [ids[1]] and first["next_cursor"]
    second = client.get(
        "/api/registry",
        params={"view": "events", "limit": 1, "q": "révision 100% _", "cursor": first["next_cursor"]},
    ).json()
    assert [row["event_id"] for row in second["items"]] == [ids[0]] and second["next_cursor"] is None
    assert expanded == [ids[1], ids[0]]
    empty = client.get("/api/registry", params={"view": "events", "q": "100% not a wildcard"}).json()
    assert empty["count"] == 0 and empty["next_cursor"] is None


def test_event_sql_bounds_zurich_dates_and_preserves_selected_date_metadata(harness):
    client, _, service, _ = harness
    ids, work_ids, _ = seed(service, 4)
    start = datetime(2026, 3, 28, 23, tzinfo=UTC)
    end = datetime(2026, 3, 29, 22, tzinfo=UTC)  # 23-hour Zurich calendar day.
    with service.db.session() as session:
        for id_, stamp in zip(
            ids, [start - timedelta(microseconds=1), start, end - timedelta(microseconds=1), end]
        ):
            session.get(RegulatoryEvent, id_).detected_at = stamp
        session.add(
            RegulatoryDate(
                entity_type="work",
                entity_id=work_ids[0],
                kind="published_at",
                date_value="2026-03-20",
                precision="day",
                provenance="official_metadata",
                evidence_json={"large": "x" * 10000},
            )
        )
        session.commit()
    result = client.get(
        "/api/registry",
        params={
            "view": "events",
            "start": "2026-03-29",
            "end": "2026-03-29",
            "kind": "act",
            "impact": "low",
            "health": "healthy",
            "connector": "registry-qa",
            "language": "fr",
            "lifecycle": "unknown",
        },
    ).json()
    assert [row["event_id"] for row in result["items"]] == [ids[2], ids[1]]
    assert result["groups"][0]["name"] == "Custom range"
    assert result["items"][0]["official_dates"]["published_at"][0]["value"] == "2026-03-20"
    assert (
        client.get(
            "/api/registry", params={"view": "events", "start": "2026-03-30", "end": "2026-03-29"}
        ).status_code
        == 422
    )


def test_privileged_event_page_still_scopes_work_visibility_and_personal_read_state(harness):
    _, _, service, _ = harness
    ids, work_ids, _ = seed(service, 3)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Registry outsider", slug="registry-outsider")
        session.add(foreign)
        session.flush()
        private = RegulatoryWork(
            owner_organization_id=foreign.id,
            authority="registry-qa",
            kind="act",
            canonical_key="private",
            title="Private outsider",
        )
        session.add(private)
        session.flush()
        session.get(RegulatoryEvent, ids[2]).work_id = private.id
        session.add_all(
            [
                RegulatoryEventUserState(
                    organization_id=service.organization_id,
                    event_id=ids[0],
                    principal_key="user:alice",
                    state="read",
                ),
                RegulatoryEventUserState(
                    organization_id=foreign.id, event_id=ids[1], principal_key="user:alice", state="read"
                ),
            ]
        )
        session.commit()
        reader = RegistryReader(service.organization_id, "alice")
        result = reader.page(session, RegistryFilters(view="events", read="read"))
        assert [row["event_id"] for row in result["items"]] == [ids[0]]
        unread = reader.page(session, RegistryFilters(view="events", read="unread"))
        assert [row["event_id"] for row in unread["items"]] == [ids[1]]
        assert (
            RegistryReader(service.organization_id, "bob").page(
                session, RegistryFilters(view="events", read="read")
            )["items"]
            == []
        )


def test_registry_keyset_index_migration_preserves_populated_events(harness):
    service = harness[2]
    ids, _, _ = seed(service, 3)
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "ff72eb61754d")
        assert "ix_regulatory_event_registry_page" not in {
            i["name"] for i in inspect(connection).get_indexes("regulatory_events")
        }
        command.upgrade(config, "head")
        assert any(
            i["name"] == "ix_regulatory_event_registry_page" and i["column_names"] == ["detected_at", "id"]
            for i in inspect(connection).get_indexes("regulatory_events")
        )
        assert set(connection.scalars(select(RegulatoryEvent.id))) == set(ids)


def test_related_watch_filter_agrees_with_details_and_excludes_foreign_watches(harness):
    client, _, service, model = harness
    law = add_law(client)
    ids, works, _ = seed(service, 2, individual=True)
    with service.db.session(include_all_organizations=True) as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"]))
        watch.active = False  # Paused watches still belong to the registry.
        for i, (subject, target) in enumerate([(works[0], mapping.work_id), (mapping.work_id, works[1])]):
            session.add(
                RegulatoryRelation(
                    subject_work_id=subject,
                    object_work_id=target,
                    authority="registry-qa",
                    relation_type="cites",
                    state="confirmed",
                    provenance_method="official_metadata",
                    dedupe_key=f"registry-link-{i}",
                    evidence_fingerprint=str(i) * 64,
                )
            )
        session.commit()
        reader = RegistryReader(service.organization_id)
        result = reader.page(
            session, RegistryFilters(view="events", authority="registry-qa", watched="watched")
        )
        assert [row["event_id"] for row in result["items"]] == list(reversed(ids))
        assert all(
            row["watched"]
            and row["linked_laws"][0]["law_id"] == law["id"]
            and not row["linked_laws"][0]["active"]
            for row in result["items"]
        )
        foreign = Organization(name="Foreign watch", slug="foreign-watch")
        session.add(foreign)
        session.flush()
        watch.organization_id = foreign.id
        session.commit()
        assert (
            reader.page(session, RegistryFilters(view="events", authority="registry-qa", watched="watched"))[
                "items"
            ]
            == []
        )
        unwatched = reader.page(
            session, RegistryFilters(view="events", authority="registry-qa", watched="unwatched")
        )
        assert len(unwatched["items"]) == 2
        assert all(not row["watched"] and row["linked_laws"] == [] for row in unwatched["items"])
        assert model.calls == []
