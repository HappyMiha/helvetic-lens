"""Visible event details use shared scalar queries without merging their evidence."""

from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_registry_event_pages import seed

from helvetic_lens.models import (
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Organization,
    RegulatoryDate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    new_id,
)
from helvetic_lens.registry import RegistryFilters, RegistryReader


def seed_details(service):
    ids, works, _ = seed(service, 50, individual=True)
    target = new_id()
    law_ids = [new_id() for _ in range(2)]
    watch_ids = [new_id() for _ in range(2)]
    with service.db.session() as session:
        session.add(
            RegulatoryWork(
                id=target, authority="detail-qa", kind="act", canonical_key=target, title="Shared target"
            )
        )
        for i, work_id in enumerate((target, works[0])):
            session.add(
                Law(
                    id=law_ids[i],
                    canonical_identity=law_ids[i],
                    name="Watched law",
                    url="https://example.test/law",
                )
            )
            session.flush()
            session.add(
                LegacyDocumentMapping(law_id=law_ids[i], work_id=work_id, mapping_status="provisional")
            )
            session.add(
                DocumentWatch(
                    id=watch_ids[i],
                    organization_id=service.organization_id,
                    law_id=law_ids[i],
                    display_name="Watch " + str(i),
                    active=bool(i),
                )
            )
        for i, work_id in enumerate(works):
            for j, (subject, obj, state) in enumerate(
                ((work_id, target, "confirmed"), (target, work_id, "proposed"), (work_id, target, "rejected"))
            ):
                session.add(
                    RegulatoryRelation(
                        subject_work_id=subject,
                        object_work_id=obj,
                        authority="detail-qa",
                        relation_type="cites",
                        state=state,
                        provenance_method="official_metadata",
                        dedupe_key=f"detail-{i}-{j}",
                        evidence_fingerprint=str(i).zfill(64),
                        evidence_json={"large": "x" * 4000},
                    )
                )
            expression = session.scalar(
                select(RegulatoryExpression).where(RegulatoryExpression.work_id == work_id)
            )
            version = RegulatoryDocumentVersion(
                expression_id=expression.id,
                version_key=work_id,
                text="x" * 4000,
                passages=[{"text": "x" * 4000}],
            )
            session.add(version)
            session.flush()
            session.get(RegulatoryEvent, ids[i]).document_version_id = version.id
            if i == 0:
                # IDs are unique per table, not across entity kinds: an unrelated older
                # version may have the same ID as a work without becoming that work's date.
                session.add(
                    RegulatoryDocumentVersion(
                        id=work_id, expression_id=expression.id, version_key="older-collision"
                    )
                )
                session.add(
                    RegulatoryDate(
                        entity_type="version",
                        entity_id=work_id,
                        kind="published_at",
                        date_value="2000-01-01",
                        precision="day",
                        provenance="official_metadata",
                        source_url="https://example.test/unselected-version",
                    )
                )

            for kind, entity_id in [
                ("work", work_id),
                ("expression", expression.id),
                ("event", ids[i]),
                ("version", version.id),
            ]:
                session.add(
                    RegulatoryDate(
                        entity_type=kind,
                        entity_id=entity_id,
                        kind="published_at",
                        date_value=f"2026-08-{i % 28 + 1:02d}",
                        precision="day",
                        provenance="official_metadata",
                        source_url=f"https://example.test/{i}/{kind}",
                        evidence_json={"large": "x" * 4000},
                    )
                )
        # A self-edge must not duplicate direct or related watched laws.
        session.add(
            RegulatoryRelation(
                subject_work_id=works[0],
                object_work_id=works[0],
                authority="detail-qa",
                relation_type="cites",
                state="confirmed",
                provenance_method="official_metadata",
                dedupe_key="self",
                evidence_fingerprint="s" * 64,
            )
        )
        session.commit()
    return ids, works, target, law_ids, watch_ids


def test_event_detail_query_count_is_constant_and_scalar_for_one_and_fifty(harness):
    _, _, service, model = harness
    ids, works, _, laws, watches = seed_details(service)
    reader = RegistryReader(service.organization_id)
    counts = []
    for size in (1, 50):
        with service.db.session() as session:
            rows = reader._event_rows(session, RegistryFilters(view="events", limit=size), None, None)[:size]
            queries, loaded = [], []

            def sql(_connection, _cursor, statement, _parameters, _context, _many):
                if statement.lstrip().upper().startswith("SELECT"):
                    queries.append(statement)

            def load(_session, value):
                loaded.append(type(value).__name__)

            sa_event.listen(service.db.engine, "before_cursor_execute", sql)
            sa_event.listen(Session, "loaded_as_persistent", load)
            try:
                reader._event_details(session, rows)
            finally:
                sa_event.remove(service.db.engine, "before_cursor_execute", sql)
                sa_event.remove(Session, "loaded_as_persistent", load)
            counts.append(len(queries))
            assert loaded == []
            assert all(
                "evidence_json" not in q and "metadata_json" not in q and "passages" not in q for q in queries
            )
            for row in rows:
                index = ids.index(row["event_id"])
                expected = set(watches) if row["work_id"] == works[0] else {watches[0]}
                assert {link["watch_id"] for link in row["linked_laws"]} == expected
                assert len(row["linked_laws"]) == len(expected)
                assert row["linked_laws"] == sorted(row["linked_laws"], key=lambda link: link["watch_id"])
                dates = row["official_dates"]["published_at"]
                assert {date["source_url"] for date in dates} == {
                    f"https://example.test/{index}/{kind}"
                    for kind in ("work", "expression", "event", "version")
                }
                assert len(dates) == 4 and all(
                    date["value"] == f"2026-08-{index % 28 + 1:02d}" for date in dates
                )
    assert counts == [3, 3]
    assert model.calls == []


def test_event_detail_links_keep_explicit_scope_in_privileged_session(harness):
    _, _, service, _ = harness
    _, _, _, laws, watches = seed_details(service)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign details", slug="foreign-registry-details")
        session.add(foreign)
        session.flush()
        session.add(DocumentWatch(organization_id=foreign.id, law_id=laws[0], display_name="Foreign watch"))
        session.commit()
        reader = RegistryReader(service.organization_id)
        filters = RegistryFilters(view="events", limit=50)
        rows = reader.page(session, filters)["items"]
        assert all(all(link["name"] != "Foreign watch" for link in row["linked_laws"]) for row in rows)
        session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == laws[0])
        ).owner_organization_id = foreign.id
        session.get(Law, laws[1]).owner_organization_id = foreign.id
        session.commit()
        rows = reader.page(session, filters)["items"]
        assert len(rows) == 50
        assert all(not row["watched"] and row["linked_laws"] == [] and row["law_id"] is None for row in rows)
        assert reader.page(session, RegistryFilters(view="events", watched="watched"))["items"] == []


def test_empty_event_details_do_not_query_and_shared_work_dates_remain_event_specific(harness):
    _, _, service, _ = harness
    ids, works, _, _, _ = seed_details(service)
    reader = RegistryReader(service.organization_id)
    with service.db.session() as session:
        # Two events on one work share work/expression dates but retain their own event/version dates.
        session.get(RegulatoryEvent, ids[1]).work_id = works[0]
        session.commit()
        rows = reader._event_rows(session, RegistryFilters(view="events", limit=50), None, None)
        reader._event_details(session, rows)
        row = next(row for row in rows if row["event_id"] == ids[1])
        assert {item["source_url"] for item in row["official_dates"]["published_at"]} == {
            "https://example.test/0/work",
            "https://example.test/0/expression",
            "https://example.test/1/event",
            "https://example.test/1/version",
        }

        def forbidden(*_args):
            raise AssertionError("Empty details queried the database")

        sa_event.listen(service.db.engine, "before_cursor_execute", forbidden)
        try:
            reader._event_details(session, [])
            reader._monitored_details(session, [])
        finally:
            sa_event.remove(service.db.engine, "before_cursor_execute", forbidden)
