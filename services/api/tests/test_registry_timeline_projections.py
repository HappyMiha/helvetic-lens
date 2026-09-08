"""Timelines read metadata, not full saved document/diff bodies or foreign state."""

from datetime import datetime, timedelta

import pytest
from conftest import add_law
from sqlalchemy import event as sa_event
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from helvetic_lens import timeline_pages
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
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
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
    Version,
    new_id,
)
from helvetic_lens.registry import RegistryReader


def collect_pages(service, law_id, initial, kind):
    items = list(initial[kind])
    info = initial["pages"][kind]
    cursors = set()
    while info["next_cursor"]:
        cursor = info["next_cursor"]
        assert cursor not in cursors
        cursors.add(cursor)
        info = service.regulatory_timeline_page(law_id, kind, cursor=cursor)
        assert len(info["items"]) <= 20
        assert info["total"] == initial["pages"][kind]["total"]
        assert info["as_of"] == initial["pages"][kind]["as_of"]
        items.extend(info["items"])
    assert len(items) == info["total"]
    return items


def without_pages(result):
    return {k: v for k, v in result.items() if k != "pages"}


def seed_timeline(harness, count=151):
    client, _, service, _ = harness
    law = add_law(client)
    stamp = utcnow() - timedelta(days=2)
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
    assert len(result["timeline"]) == len(result["source_provenance"]) == 20
    entries = collect_pages(service, law_id, result, "timeline")
    assert set("version:" + id_ for id_ in versions + [original]) <= {row["id"] for row in entries}
    assert set("event:" + id_ for id_ in events) <= {row["id"] for row in entries}
    assert set("comparison:" + id_ for id_ in comparisons) <= {row["id"] for row in entries}
    assert len({row["id"] for row in entries}) == len(entries)
    assert entries == sorted(entries, key=lambda row: (row["at"] or "", row["id"]), reverse=True)
    assert result["normalized_versions"] == 152
    observed = collect_pages(service, law_id, result, "source_provenance")
    assert [
        item["source_url"] for item in observed if item["source_url"].startswith("https://example.test/")
    ] == ["https://example.test/" + id_ for id_ in sorted(observations, reverse=True)]
    observation_query = next(q for q in queries if "FROM observations" in q and "LIMIT" in q)
    assert "LIMIT" in observation_query
    assert len(queries) == 12
    response = client.get(f"/api/laws/{law_id}/timeline")
    assert response.status_code == 200
    assert {k: v for k, v in response.json().items() if k != "pages"} == {
        k: v for k, v in result.items() if k != "pages"
    }
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
    assert len(result["relations"]) == 20 and len(queries) == 12
    relations = collect_pages(service, law["id"], result, "relations")
    assert len(relations) == 50
    assert {item["other_work_id"] for item in relations} == set(others[:50])
    for item in relations:
        index = others.index(item["other_work_id"])
        assert item["direction"] == ("outgoing" if index % 2 else "incoming")
        assert item["reciprocal_label"] == ("predecessor" if index % 2 else "successor")
        assert item["other_law_id"] == (aliases[2] if index == 0 else None)
    assert client.get(f"/api/laws/{aliases[2]}/timeline").status_code == 200
    with service.db.session() as session:
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == aliases[2])).active = False
        session.commit()
    assert len(record_timeline(service, law["id"])[1]) == 12
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
        assert len(queries) == 5
        assert without_pages(client.get(f"/api/laws/{law['id']}/timeline").json()) == without_pages(result)
        assert all(
            result["pages"][kind]["total"] == 0 for kind in ("relations", "identifiers", "expressions")
        )


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
                created_at=utcnow() - timedelta(days=1),
            )
        )
        session.commit()
    result, _ = record_timeline(service, law_id, privileged=True)
    ids = {item["id"] for item in result["timeline"]}
    assert "version:" + versions[0] not in ids and "comparison:" + comparisons[0] not in ids
    assert "version:" + versions[1] in ids and "comparison:" + comparisons[1] in ids
    assert result["normalized_versions"] == 2
    assert len(result["source_provenance"]) == 20
    observations = collect_pages(service, law_id, result, "source_provenance")
    assert len(observations) == 502
    assert not any("private.test" in item["source_url"] for item in observations)
    assert without_pages(client.get(f"/api/laws/{law_id}/timeline").json()) == without_pages(result)


def test_large_metadata_pages_and_detail_remain_complete(harness):
    client, fetcher, service, model = harness
    law = add_law(client)
    with service.db.session() as session:
        work = session.scalar(
            select(LegacyDocumentMapping.work_id).where(LegacyDocumentMapping.law_id == law["id"])
        )
        stamp = utcnow() - timedelta(days=1)
        for i in range(121):
            session.add(
                RegulatoryIdentifier(
                    work_id=work,
                    authority="qa",
                    scheme="qa",
                    value=f"Value {i:03}",
                    normalized_value=f"qa{i}",
                    source_url=f"https://example.test/{i}",
                    created_at=stamp,
                )
            )
            session.add(
                RegulatoryExpression(
                    work_id=work,
                    language="de",
                    expression_key=f"qa{i}",
                    title=f"Title {i:03}",
                    metadata_json={"large": "BODY" * 1000},
                    created_at=stamp,
                )
            )
        session.commit()
    fetches = len(fetcher.calls)
    result, _ = record_timeline(service, law["id"])
    for kind, key in (("identifiers", "value"), ("expressions", "title")):
        assert len(result[kind]) == 20
        items = collect_pages(service, law["id"], result, kind)
        assert len(items) >= 121
        assert len({item[key] for item in items}) == len(items)
        for cursor in ("", result["pages"][kind]["first_cursor"]):
            response = client.get(f"/api/laws/{law['id']}/timeline/{kind}", params={"cursor": cursor})
            assert response.status_code == 200
            assert response.json()["items"] == result[kind]
        for paged in (False, True):
            detail = client.get(f"/api/laws/{law['id']}", params={"paged_history": paged}).json()
            assert detail["regulatory_timeline"][kind] == result[kind]
            assert detail["regulatory_timeline"]["pages"][kind]["total"] == len(items)
    assert len(fetcher.calls) == fetches and model.calls == []


def test_timeline_cutoff_ties_deletion_and_late_backdated_detection(harness, monkeypatch):
    client, _, service, _ = harness
    law_id, work, _, _, events, _, _ = seed_timeline(harness, count=35)
    cutoff = utcnow()
    monkeypatch.setattr(timeline_pages, "utcnow", lambda: cutoff)
    first = service.regulatory_timeline_page(law_id, "timeline", limit=10)
    before = []
    info = first
    while True:
        before.extend(info["items"])
        if not info["next_cursor"]:
            break
        info = service.regulatory_timeline_page(law_id, "timeline", limit=10, cursor=info["next_cursor"])
    # Deleting the cursor boundary must not make the next page skip or duplicate anything.
    event_page = next(item for item in before if item["id"] == "event:" + events[0])
    position = timeline_pages.Cursor(
        organization_id=service.organization_id,
        law_id=law_id,
        work_id=work,
        kind="timeline",
        limit=10,
        as_of=cutoff,
        at=datetime.fromisoformat(event_page["at"]),
        key=event_page["id"],
    )
    with service.db.session() as session:
        session.delete(session.get(RegulatoryEvent, events[0]))
        session.add(
            RegulatoryEvent(
                work_id=work,
                authority="qa",
                event_type="new_version",
                dedupe_key="late-backdated",
                detected_at=cutoff - timedelta(days=10),
                created_at=cutoff + timedelta(seconds=1),
                provenance_method="official_metadata",
            )
        )
        session.commit()
    after = service.regulatory_timeline_page(
        law_id, "timeline", limit=10, cursor=timeline_pages.encoded(position)
    )
    index = next(i for i, item in enumerate(before) if item["id"] == event_page["id"])
    assert after["items"] == before[index + 1 : index + 11]
    assert after["total"] == first["total"] - 1
    # A new first traversal can include new admissions; the saved traversal cannot.
    monkeypatch.setattr(timeline_pages, "utcnow", lambda: cutoff + timedelta(seconds=2))
    assert service.regulatory_timeline_page(law_id, "timeline")["total"] == first["total"]
    assert (
        service.regulatory_timeline_page(law_id, "timeline", limit=10, cursor=first["first_cursor"])["total"]
        == first["total"] - 1
    )


def test_page_cursor_contract_and_access_are_rechecked(harness):
    client, _, service, _ = harness
    law_id, work, *_ = seed_timeline(harness, count=2)
    first = service.regulatory_timeline_page(law_id, "timeline")
    url = f"/api/laws/{law_id}/timeline/timeline"
    position = timeline_pages.Cursor(
        organization_id=service.organization_id,
        law_id=law_id,
        work_id=work,
        kind="timeline",
        limit=20,
        as_of=datetime.fromisoformat(first["as_of"]),
    )
    for update in (
        {"organization_id": "foreign"},
        {"law_id": new_id()},
        {"work_id": new_id()},
        {"kind": "expressions"},
        {"limit": 50},
        {"key": "unpaired"},
        {"as_of": utcnow() + timedelta(days=1)},
    ):
        cursor = timeline_pages.encoded(position.model_copy(update=update))
        assert client.get(url, params={"cursor": cursor}).status_code == 422
    for params in ({"cursor": "!garbage!"}, {"cursor": "a" * 2049}, {"limit": 0}, {"limit": 51}):
        assert client.get(url, params=params).status_code == 422
    assert client.get(f"/api/laws/{law_id}/timeline/unsupported").status_code == 422
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        watch.active = False
        session.commit()
    assert client.get(url, params={"cursor": first["first_cursor"]}).status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Other", slug="timeline-cursor-other")
        session.add(foreign)
        session.flush()
        session.scalar(
            select(DocumentWatch).where(DocumentWatch.law_id == law_id)
        ).organization_id = foreign.id
        session.commit()
    for kind in timeline_pages.KINDS:
        with service.db.session(include_all_organizations=True) as session:
            with pytest.raises(DomainError) as exc:
                timeline_pages.page(session, RegistryReader(service.organization_id), law_id, kind)
            assert exc.value.status == 404
        assert (
            client.get(
                f"/api/laws/{law_id}/timeline/{kind}", params={"cursor": first["first_cursor"]}
            ).status_code
            == 404
        )
