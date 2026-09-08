"""Timelines read metadata, not full saved document/diff bodies or foreign state."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import add_law
from sqlalchemy import event as sa_event
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Observation,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    Version,
    new_id,
)
from helvetic_lens.registry import RegistryReader


def seed_timeline(harness, count=151):
    client, _, service, _ = harness
    law = add_law(client)
    stamp = datetime.now(UTC)
    versions = [new_id() for _ in range(count)]
    events = [new_id() for _ in range(count)]
    comparisons = [new_id() for _ in range(count)]
    with service.db.session() as session:
        work = session.scalar(
            select(LegacyDocumentMapping.work_id).where(LegacyDocumentMapping.law_id == law["id"])
        )
        expression = session.scalar(
            select(RegulatoryExpression.id).where(RegulatoryExpression.work_id == work)
        )
        original = session.scalar(select(Version.id).where(Version.law_id == law["id"]))
        session.execute(
            insert(Version),
            [
                dict(
                    id=id_,
                    law_id=law["id"],
                    title="Saved version",
                    content_hash=id_.replace("-", "").ljust(64, "0"),
                    extractor="qa",
                    text="DOCUMENT BODY " * 2000,
                    passages=[{"text": "passage" * 2000}],
                    content_type="text/plain",
                    artifact_key="unused-qa",
                    filename="qa.txt",
                    origin="import",
                    declared_date="2026-08-01",
                    created_at=stamp,
                )
                for id_ in versions
            ],
        )
        session.execute(
            insert(Comparison),
            [
                dict(
                    id=id_,
                    law_id=law["id"],
                    old_version_id=original,
                    new_version_id=versions[i],
                    mode="historical",
                    diff={"large": "DIFF BODY " * 2000},
                    created_at=stamp,
                )
                for i, id_ in enumerate(comparisons)
            ],
        )
        session.execute(
            insert(RegulatoryDocumentVersion),
            [
                dict(
                    expression_id=expression,
                    version_key=id_,
                    text="NORMALIZED BODY " * 2000,
                    passages=[{"text": "normalized passage" * 2000}],
                    created_at=stamp,
                )
                for id_ in versions
            ],
        )
        session.execute(
            insert(RegulatoryEvent),
            [
                dict(
                    id=id_,
                    work_id=work,
                    authority="qa",
                    event_type="new_version",
                    dedupe_key=id_,
                    detected_at=stamp,
                    provenance_method="official_metadata",
                    source_url="https://example.test/event/" + id_,
                    evidence_json={"large": "EVENT EVIDENCE " * 2000},
                )
                for id_ in events
            ],
        )
        observations = [f"99000000-0000-0000-0000-{i:012d}" for i in range(501)]
        session.execute(
            insert(Observation),
            [
                dict(
                    id=id_,
                    organization_id=service.organization_id,
                    law_id=law["id"],
                    version_id=original,
                    origin="live",
                    filename="qa.txt",
                    artifact_key="unused-qa",
                    source_url="https://example.test/" + id_,
                    metadata_json={"large": "OBSERVATION BODY " * 1000},
                    created_at=stamp + timedelta(days=1),
                )
                for id_ in observations
            ],
        )
        session.commit()
    return law["id"], work, original, versions, events, comparisons, observations


def record_timeline(service, law_id, *, privileged=False):
    queries, loaded = [], []

    def sql(_connection, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    def load(_session, value):
        loaded.append(type(value).__name__)

    sa_event.listen(service.db.engine, "before_cursor_execute", sql)
    sa_event.listen(Session, "loaded_as_persistent", load)
    try:
        with service.db.session(include_all_organizations=privileged) as session:
            result = RegistryReader(service.organization_id).timeline(session, law_id)
    finally:
        sa_event.remove(service.db.engine, "before_cursor_execute", sql)
        sa_event.remove(Session, "loaded_as_persistent", load)
    assert loaded == []
    assert all(
        not any(
            column in q
            for column in ("passages", "evidence_json", "metadata_json", "versions.text", "comparisons.diff")
        )
        for q in queries
    )
    return result, queries


def test_large_timeline_preserves_all_entries_without_hydrating_saved_bodies(harness):
    client, fetcher, service, model = harness
    law_id, work, original, versions, events, comparisons, observations = seed_timeline(harness)
    fetches = len(fetcher.calls)
    result, queries = record_timeline(service, law_id)
    entries = result["timeline"]
    assert set("version:" + id_ for id_ in versions + [original]) <= {row["id"] for row in entries}
    assert set("event:" + id_ for id_ in events) <= {row["id"] for row in entries}
    assert set("comparison:" + id_ for id_ in comparisons) <= {row["id"] for row in entries}
    assert len({row["id"] for row in entries}) == len(entries)
    assert entries == sorted(entries, key=lambda row: (row["at"] or "", row["id"]), reverse=True)
    assert result["normalized_versions"] == 152
    assert [item["source_url"] for item in result["source_provenance"]] == [
        "https://example.test/" + id_ for id_ in sorted(observations, reverse=True)[:100]
    ]
    observation_query = next(q for q in queries if "FROM observations" in q)
    assert "LIMIT" in observation_query
    assert len(queries) == 9
    response = client.get(f"/api/laws/{law_id}/timeline")
    assert response.status_code == 200 and response.json() == result
    assert len(fetcher.calls) == fetches and model.calls == []


def test_timeline_relation_fanout_uses_one_scoped_alias_query(harness):
    client, _, service, model = harness
    law = add_law(client)
    with service.db.session(include_all_organizations=True) as session:
        work = session.scalar(
            select(LegacyDocumentMapping.work_id).where(LegacyDocumentMapping.law_id == law["id"])
        )
        foreign = Organization(name="Foreign timeline", slug="foreign-timeline")
        session.add(foreign)
        session.flush()
        others = [new_id() for _ in range(51)]
        session.execute(
            insert(RegulatoryWork),
            [
                dict(
                    id=id_,
                    authority="qa",
                    kind="act",
                    canonical_key=id_,
                    title="Other " + str(i),
                    owner_organization_id=foreign.id if i == 50 else None,
                )
                for i, id_ in enumerate(others)
            ],
        )
        session.execute(
            insert(RegulatoryRelation),
            [
                dict(
                    subject_work_id=work if i % 2 else other,
                    object_work_id=other if i % 2 else work,
                    authority="qa",
                    relation_type="replaces",
                    state="confirmed",
                    provenance_method="official_metadata",
                    dedupe_key=other,
                    evidence_fingerprint="e" * 64,
                    evidence_json={"large": "RELATION BODY " * 2000},
                )
                for i, other in enumerate(others)
            ],
        )
        aliases = [new_id() for _ in range(4)]
        session.execute(
            insert(Law),
            [
                dict(id=id_, canonical_identity=id_, name="Alias", url="https://example.test/" + id_)
                for id_ in aliases
            ],
        )
        session.execute(
            insert(LegacyDocumentMapping),
            [dict(law_id=id_, work_id=others[0], mapping_status="provisional") for id_ in aliases],
        )
        # Foreign active, own paused, own active, visible but unmonitored.
        session.execute(
            insert(DocumentWatch),
            [
                dict(
                    organization_id=foreign.id if i == 0 else service.organization_id,
                    law_id=id_,
                    display_name="Alias",
                    active=i != 1,
                )
                for i, id_ in enumerate(aliases[:3])
            ],
        )
        session.commit()
    result, queries = record_timeline(service, law["id"], privileged=True)
    assert len(result["relations"]) == 50 and len(queries) == 9
    for item in result["relations"]:
        index = others.index(item["other_work_id"])
        assert item["direction"] == ("outgoing" if index % 2 else "incoming")
        assert item["reciprocal_label"] == ("predecessor" if index % 2 else "successor")
        assert item["other_law_id"] == (aliases[2] if index == 0 else None)
    assert client.get(f"/api/laws/{aliases[2]}/timeline").status_code == 200
    with service.db.session() as session:
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == aliases[2])).active = False
        session.commit()
    assert len(record_timeline(service, law["id"])[1]) == 9
    assert model.calls == []


@pytest.mark.parametrize("hidden", ["law", "watch", "mapping", "work"])
def test_timeline_header_explicit_scope_and_legacy_fallback(harness, hidden):
    client, _, service, _ = harness
    law = add_law(client)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Private timeline", slug="private-timeline")
        session.add(foreign)
        session.flush()
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        model = {
            "law": Law,
            "work": RegulatoryWork,
            "mapping": LegacyDocumentMapping,
            "watch": DocumentWatch,
        }[hidden]
        obj = (
            session.get(model, law["id"] if hidden == "law" else mapping.work_id)
            if hidden in {"law", "work"}
            else mapping
            if hidden == "mapping"
            else session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"]))
        )
        setattr(obj, "organization_id" if hidden == "watch" else "owner_organization_id", foreign.id)
        session.commit()
    if hidden in {"law", "watch"}:
        with pytest.raises(DomainError) as exc:
            record_timeline(service, law["id"], privileged=True)
        assert exc.value.status == 404
        assert client.get(f"/api/laws/{law['id']}/timeline").status_code == 404
    else:
        result, queries = record_timeline(service, law["id"], privileged=True)
        assert result["work"]["id"] is None and result["work"]["kind"] == "unclassified_document"
        assert (
            result["relations"] == [] and result["normalized_versions"] == 0 and result["identifiers"] == []
        )
        assert result["expressions"] == [] and not any(row["type"] == "event" for row in result["timeline"])
        assert any(row["type"] == "version" for row in result["timeline"])
        assert len(queries) == 4
        assert client.get(f"/api/laws/{law['id']}/timeline").json() == result


def test_timeline_private_history_and_observation_scope(harness):
    client, _, service, _ = harness
    law_id, _, original, versions, _, comparisons, _ = seed_timeline(harness, count=2)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Private history", slug="private-timeline-history")
        session.add(foreign)
        session.flush()
        session.get(Version, versions[0]).owner_organization_id = foreign.id
        session.get(Comparison, comparisons[0]).owner_organization_id = foreign.id
        normalized = session.scalar(
            select(RegulatoryDocumentVersion).where(RegulatoryDocumentVersion.version_key == versions[0])
        )
        normalized.legacy_version_id = versions[0]
        session.add(
            Observation(
                organization_id=foreign.id,
                law_id=law_id,
                version_id=original,
                origin="import",
                filename="foreign.txt",
                artifact_key="foreign",
                source_url="https://private.test/secret",
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
        session.commit()
    result, _ = record_timeline(service, law_id, privileged=True)
    ids = {item["id"] for item in result["timeline"]}
    assert "version:" + versions[0] not in ids and "comparison:" + comparisons[0] not in ids
    assert "version:" + versions[1] in ids and "comparison:" + comparisons[1] in ids
    assert result["normalized_versions"] == 2
    assert len(result["source_provenance"]) == 100
    assert not any("private.test" in item["source_url"] for item in result["source_provenance"])
    assert client.get(f"/api/laws/{law_id}/timeline").json() == result
