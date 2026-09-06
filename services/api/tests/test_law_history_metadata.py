"""The real document detail keeps metadata without hydrating historical text/diffs."""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_registry_timeline_projections import seed_timeline

from helvetic_lens import law_history
from helvetic_lens.models import Comparison, DocumentWatch, Law, Observation, Organization, Version
from helvetic_lens.service import as_dict, version_summary


@contextmanager
def recording(service):
    queries, loaded = [], []

    def sql(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    def load(_session, value):
        if isinstance(value, (Version, Comparison, Observation)):
            loaded.append((type(value).__name__, value.id))

    sa_event.listen(service.db.engine, "before_cursor_execute", sql)
    sa_event.listen(Session, "loaded_as_persistent", load)
    try:
        yield queries, loaded
    finally:
        sa_event.remove(service.db.engine, "before_cursor_execute", sql)
        sa_event.remove(Session, "loaded_as_persistent", load)


def prepare(harness, count=151):
    result = seed_timeline(harness, count=count)
    _, _, service, _ = harness
    law_id, _, _, versions, _, comparison_ids, _ = result
    with service.db.session() as session:
        for index, id_ in enumerate(comparison_ids):
            comparison = session.get(Comparison, id_)
            comparison.diff = {
                "counts": {"added": index, "removed": 0, "modified": 2, "unchanged": 3},
                "large": "DIFF BODY " * 2000,
            }
        for i, id_ in enumerate(versions):
            version = session.get(Version, id_)
            version.text = "Révision 👁️ Artikel 漢字\n" * 2000
            version.passages = (
                [{"text": "Saved source " * 2000, "page": value} for value in (None, 0, 2, 19)]
                if i % 2
                else []
            )
        session.commit()
    return result


def test_law_detail_large_history_is_metadata_compatible_without_historical_body_loads(harness):
    client, fetcher, service, model = harness
    law_id, _, original, ids, _, comparison_ids, _ = prepare(harness)
    with service.db.session() as session:
        expected_versions = [
            version_summary(row)
            for row in session.scalars(
                select(Version)
                .where(Version.law_id == law_id)
                .order_by(Version.created_at.desc(), Version.id.desc())
            )
        ]
        expected_comparisons = [
            as_dict(row, {"diff"}) | {"counts": row.diff["counts"]}
            for row in session.scalars(
                select(Comparison)
                .where(Comparison.law_id == law_id)
                .order_by(Comparison.created_at.desc(), Comparison.id.desc())
                .limit(50)
            )
        ]
        expected_observations = [
            as_dict(row, {"artifact_key"})
            for row in session.scalars(
                select(Observation)
                .where(Observation.law_id == law_id)
                .order_by(Observation.created_at.desc(), Observation.id.desc())
                .limit(100)
            )
        ]
    before = len(fetcher.calls)
    with recording(service) as (queries, loaded):
        response = client.get("/api/laws/" + law_id)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["versions"] == expected_versions
    assert data["comparisons"] == expected_comparisons
    assert data["observations"] == expected_observations
    assert (
        len(data["versions"]) == 152 and len(data["comparisons"]) == 50 and len(data["observations"]) == 100
    )
    assert {id_ for kind, id_ in loaded if kind == "Version"} == {original}
    assert len([item for item in loaded if item[0] == "Comparison"]) == 1
    assert not any(kind == "Observation" for kind, _ in loaded)
    assert data["current_version"]["id"] == original
    assert model.calls == [] and len(fetcher.calls) == before
    with recording(service) as (metadata_queries, metadata_loaded):
        with service.db.session() as session:
            assert law_history.versions(session, service.organization_id, law_id) == expected_versions
            assert law_history.comparisons(session, service.organization_id, law_id) == expected_comparisons
            assert law_history.observations(session, service.organization_id, law_id) == expected_observations
    assert len(metadata_queries) == 3 and metadata_loaded == []
    assert all("versions.artifact_key" not in query for query in metadata_queries)


def test_law_history_keeps_scope_in_privileged_sessions(harness):
    _, _, service, _ = harness
    law_id, _, original, versions, _, comparisons, _ = prepare(harness, count=2)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign metadata", slug="foreign-history-metadata")
        session.add(foreign)
        session.flush()
        session.get(Version, versions[0]).owner_organization_id = foreign.id
        session.get(Comparison, comparisons[0]).owner_organization_id = foreign.id
        session.add(
            Observation(
                organization_id=foreign.id,
                law_id=law_id,
                version_id=original,
                origin="live",
                source_url="https://foreign.test/secret",
                filename="secret",
                artifact_key="secret",
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
        session.commit()
        assert {row["id"] for row in law_history.versions(session, service.organization_id, law_id)} == {
            original,
            versions[1],
        }
        assert {row["id"] for row in law_history.comparisons(session, service.organization_id, law_id)} == {
            comparisons[1]
        }
        assert all(
            "foreign.test" not in row["source_url"]
            for row in law_history.observations(session, service.organization_id, law_id)
        )
        session.scalar(
            select(DocumentWatch).where(DocumentWatch.law_id == law_id)
        ).organization_id = foreign.id
        session.commit()
        for reader in (law_history.versions, law_history.comparisons, law_history.observations):
            assert reader(session, service.organization_id, law_id) == []
        session.scalar(
            select(DocumentWatch).where(DocumentWatch.law_id == law_id)
        ).organization_id = service.organization_id
        session.get(Law, law_id).owner_organization_id = foreign.id
        session.commit()
        for reader in (law_history.versions, law_history.comparisons, law_history.observations):
            assert reader(session, service.organization_id, law_id) == []


@pytest.mark.parametrize(
    "pages,expected", [([], 0), ([None, 0, None], 0), ([2, None, 12, 3], 12), ([1, 2.5], 2.5)]
)
def test_saved_page_statistics_and_unicode_match_existing_metadata(harness, pages, expected):
    _, _, service, _ = harness
    law_id, _, _, ids, _, _, _ = prepare(harness, count=1)
    with service.db.session() as session:
        version = session.get(Version, ids[0])
        version.text = "ä👁️漢字\n"
        version.passages = [{"page": page, "text": "source"} for page in pages]
        session.commit()
        result = next(
            item
            for item in law_history.versions(session, service.organization_id, law_id)
            if item["id"] == ids[0]
        )
        assert result["page_count"] == expected
        assert result["passage_count"] == len(pages)
        assert result["characters"] == len("ä👁️漢字\n")
        assert result == version_summary(version)
