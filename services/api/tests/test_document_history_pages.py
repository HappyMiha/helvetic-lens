"""Complete saved history through bounded metadata pages, without inference."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, inspect, select, update
from test_law_history_metadata import prepare as prepare_metadata
from test_law_history_metadata import recording

from helvetic_lens import law_history
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import Comparison, DocumentWatch, Law, Observation, Organization, Version, new_id


def prepare(harness, count=151):
    result = prepare_metadata(harness, count=count)
    # The shared timeline fixture intentionally contains future-dated saves.
    # This traversal corpus instead has tied, already-saved records on every table.
    with harness[2].db.session() as session:
        stamp = utcnow() - timedelta(days=30)
        for model in (Version, Comparison, Observation):
            session.execute(update(model).where(model.law_id == result[0]).values(created_at=stamp))
        session.commit()
    return result


@pytest.mark.parametrize("kind", ["versions", "comparisons", "observations"])
def test_complete_history_pages_are_bounded_and_keep_equal_time_order(harness, kind):
    client, fetcher, service, model = harness
    law_id, *_ = prepare(harness, count=151)
    record_type = law_history.READERS[kind][0]
    with service.db.session() as session:
        expected = list(
            session.scalars(
                select(record_type.id)
                .where(record_type.law_id == law_id)
                .order_by(record_type.created_at.desc(), record_type.id.desc())
            )
        )
    before_fetches = len(fetcher.calls)
    cursor, found, cutoff, first_cursor = "", [], None, None
    while True:
        with recording(service) as (queries, loaded):
            response = client.get(
                f"/api/laws/{law_id}/history/{kind}", params={"cursor": cursor, "limit": 20}
            )
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["total"] == len(expected) and len(page["items"]) <= 20
        # Four history reads plus the HTTP service's three configuration reads.
        assert loaded == [] and len(queries) == 7
        assert all("artifact_key" not in query for query in queries)
        assert all("text" not in row and "passages" not in row and "diff" not in row for row in page["items"])
        found.extend(item["id"] for item in page["items"])
        cutoff, first_cursor = cutoff or page["as_of"], first_cursor or page["first_cursor"]
        assert page["as_of"] == cutoff and page["first_cursor"] == first_cursor
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert found == expected and len(set(found)) == len(expected)
    assert len(expected) > (100 if kind == "observations" else 50)
    first = client.get(f"/api/laws/{law_id}/history/{kind}", params={"cursor": first_cursor}).json()
    assert [item["id"] for item in first["items"]] == expected[:20]
    assert len(fetcher.calls) == before_fetches and model.calls == []


def test_paged_document_detail_opt_in_keeps_current_version_and_legacy_contract(harness):
    client, _, service, _ = harness
    law_id, _, original, *_ = prepare(harness, count=51)
    with recording(service) as (_, loaded):
        response = client.get(f"/api/laws/{law_id}", params={"paged_history": True})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["current_version"]["id"] == original
    assert {id_ for kind, id_ in loaded if kind == "Version"} == {original}
    for kind in law_history.READERS:
        assert len(value[kind]) == 20
        assert value["history_pages"][kind]["total"] > 50
        assert value["history_pages"][kind]["next_cursor"]
    legacy = client.get(f"/api/laws/{law_id}").json()
    assert (
        len(legacy["versions"]) == 52
        and len(legacy["comparisons"]) == 50
        and len(legacy["observations"]) == 100
    )
    assert "history_pages" not in legacy


def test_first_cursor_includes_exact_cutoff_without_id_collation_sentinel(harness, monkeypatch):
    client, _, service, _ = harness
    law_id, *_ = prepare(harness, count=31)
    stamp = utcnow()
    with service.db.session() as session:
        session.execute(update(Version).where(Version.law_id == law_id).values(created_at=stamp))
        session.commit()
    monkeypatch.setattr(law_history, "utcnow", lambda: stamp)
    path = f"/api/laws/{law_id}/history/versions"
    first = client.get(path).json()
    assert first["total"] == 32 and len(first["items"]) == 20
    back = client.get(path, params={"cursor": first["first_cursor"]}).json()
    assert back == first
    last = client.get(path, params={"cursor": first["next_cursor"]}).json()
    assert len(last["items"]) == 12 and last["next_cursor"] is None


def test_cursor_survives_boundary_deletion_and_excludes_new_saves(harness):
    client, _, service, _ = harness
    law_id, _, original, *_ = prepare(harness, count=41)
    path = f"/api/laws/{law_id}/history/observations"
    first = client.get(path).json()
    with service.db.session() as session:
        expected = list(
            session.scalars(
                select(Observation.id)
                .where(Observation.law_id == law_id)
                .order_by(Observation.created_at.desc(), Observation.id.desc())
            )
        )
        session.execute(delete(Observation).where(Observation.id == first["items"][-1]["id"]))
        late = Observation(
            id=new_id(),
            organization_id=service.organization_id,
            law_id=law_id,
            version_id=original,
            origin="live",
            filename="late.txt",
            artifact_key="test-only",
            created_at=utcnow() + timedelta(seconds=1),
        )
        session.add(late)
        session.commit()
        late_id = late.id
    second = client.get(path, params={"cursor": first["next_cursor"]}).json()
    assert [item["id"] for item in second["items"]] == expected[20:40]
    assert late_id not in [item["id"] for item in second["items"]]
    assert second["total"] == first["total"] - 1


@pytest.mark.parametrize("fault", ["kind", "law", "organization", "limit", "malformed", "future", "extra", "partial_position"])
def test_cursor_is_typed_and_bound_to_history_scope(harness, fault):
    import base64
    import json

    client, _, service, _ = harness
    law_id, *_ = prepare(harness, count=21)
    cursor = client.get(f"/api/laws/{law_id}/history/versions").json()["next_cursor"]
    raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    if fault == "kind":
        raw["kind"] = "comparisons"
    if fault == "law":
        raw["law_id"] = new_id()
    if fault == "organization":
        raw["organization_id"] = new_id()
    if fault == "limit":
        raw["limit"] = 50
    if fault == "future":
        raw["as_of"] = (utcnow() + timedelta(days=2)).isoformat()
    if fault == "extra":
        raw["skip_access"] = True
    if fault == "partial_position":
        raw["at"] = None
    cursor = (
        "not a cursor"
        if fault == "malformed"
        else base64.urlsafe_b64encode(json.dumps(raw).encode()).decode()
    )
    response = client.get(f"/api/laws/{law_id}/history/versions", params={"cursor": cursor})
    assert response.status_code == 422 and response.json()["code"] == "invalid_history_page"
    with service.db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError):
            law_history.page(session, service.organization_id, law_id, "versions", limit=True)


def test_history_pages_recheck_watch_and_private_evidence_even_when_privileged(harness):
    client, _, service, _ = harness
    law_id, _, original, ids, *_ = prepare(harness, count=21)
    first = client.get(f"/api/laws/{law_id}/history/versions").json()
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign history", slug="foreign-paged-history")
        session.add(foreign)
        session.flush()
        session.get(Version, ids[0]).owner_organization_id = foreign.id
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        watch.active = False
        session.commit()
        page = law_history.page(session, service.organization_id, law_id, "versions", limit=50)
        assert page["total"] == 21 and ids[0] not in [item["id"] for item in page["items"]]
        assert original in [item["id"] for item in page["items"]]
        session.get(Law, law_id).owner_organization_id = foreign.id
        session.commit()
        with pytest.raises(DomainError) as error:
            law_history.page(session, service.organization_id, law_id, "versions")
        assert error.value.status == 404
        session.get(Law, law_id).owner_organization_id = None
        watch.organization_id = foreign.id
        session.commit()
    response = client.get(f"/api/laws/{law_id}/history/versions", params={"cursor": first["next_cursor"]})
    assert response.status_code == 404


def test_history_indexes_migrate_without_rewriting_evidence(harness):
    from alembic.config import Config

    from alembic import command

    _, _, service, _ = harness
    law_id, *_ = prepare(harness, count=2)
    with service.db.session() as session:
        before = law_history.versions(session, service.organization_id, law_id)
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "c3a5be941872")
        assert not any(
            row["name"] == "ix_versions_law_saved_page" for row in inspect(connection).get_indexes("versions")
        )
        command.upgrade(config, "head")
        for table, name in [
            ("versions", "ix_versions_law_saved_page"),
            ("comparisons", "ix_comparisons_law_saved_page"),
            ("observations", "ix_observations_org_law_saved_page"),
        ]:
            assert name in {row["name"] for row in inspect(connection).get_indexes(table)}
    with service.db.session() as session:
        assert law_history.versions(session, service.organization_id, law_id) == before


def test_authenticated_viewer_history_is_passive_and_membership_revocation_takes_effect(tmp_path):
    from conftest import LAW_URL, FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_administration import csrf, register, settings

    from helvetic_lens.main import create_app
    from helvetic_lens.models import OrganizationMembership

    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        assert client.get("/api/laws/missing/history/versions").status_code == 401
        identity = register(client, "history-reader@example.invalid")
        created = client.post("/api/laws", json={"url": LAW_URL, "synthetic": True}, headers=csrf(client))
        assert created.status_code == 201, created.text
        path = f"/api/laws/{created.json()['id']}/history/versions"
        assert client.get(path).status_code == 200
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
            )
            membership.role = "viewer"
            session.commit()
        result = client.get(path)
        assert result.status_code == 200 and len(result.json()["items"]) == 1
        assert client.delete(f"/api/laws/{created.json()['id']}", headers=csrf(client)).status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.execute(
                delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
            )
            session.commit()
        assert client.get(path).status_code in {401, 403}
        session_response = client.get("/api/auth/session")
        assert session_response.status_code == 200 and not session_response.json()["authenticated"]
