"""Large saved evidence is paged in SQL without hydrating a full version."""

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session
from test_corpus_evidence import saved
from test_workflow import add_law

from helvetic_lens.evidence_pages import TEXT_PAGE_SIZE
from helvetic_lens.models import (
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryWork,
    Version,
)


def seed(harness, native):
    client, _, service, _ = harness
    if native:
        version_id, event_id, _ = saved(harness)
        model = RegulatoryDocumentVersion
    else:
        version_id = add_law(client)["current_version_id"]
        event_id = None
        model = Version
    return (
        client,
        service,
        model,
        version_id,
        event_id,
        f"/api/{'regulatory-versions' if native else 'versions'}/{version_id}/page",
    )


@pytest.mark.parametrize("native", [False, True])
def test_large_evidence_exact_target_and_sql_pages_without_full_orm_load(harness, native):
    client, service, model, version_id, _, url = seed(harness, native)
    with service.db.session() as session:
        version = session.get(model, version_id)
        version.passages = [
            {"id": f"p{i}", "text": f"Saved legal passage {i} " + "x" * 200, "page": i // 20 + 1}
            for i in range(10001)
        ]
        version.text = "Original saved complete text " * 100000
        session.commit()
    hydrated = []

    def loaded(session, obj):
        if isinstance(obj, (Version, RegulatoryDocumentVersion)):
            hydrated.append(obj.id)

    sa_event.listen(Session, "loaded_as_persistent", loaded)
    try:
        response = client.get(url, params={"passage": "p9999"})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["pagination"]["offset"] == 9950 and data["pagination"]["total"] == 10001
        assert data["pagination"]["target_found"] and len(data["passages"]) == 50
        assert data["passages"][-1]["id"] == "p9999" and len(response.content) < 20000
        assert "text" not in data and data["plain_text"] is None
        tail = client.get(url, params={"offset": data["pagination"]["next_offset"]}).json()
        assert [p["id"] for p in tail["passages"]] == ["p10000"] and tail["pagination"]["next_offset"] is None
        missing = client.get(url, params={"passage": "not-saved"}).json()
        assert missing["pagination"]["target_found"] is False
        assert hydrated == []
    finally:
        sa_event.remove(Session, "loaded_as_persistent", loaded)
    assert harness[3].calls == []


@pytest.mark.parametrize("native", [False, True])
def test_plain_text_pages_preserve_every_character_and_empty_state(harness, native):
    client, service, model, version_id, _, url = seed(harness, native)
    original = "Art. 1 — ÄÖÜ français italiano rumantsch 👀\n" * 1200
    with service.db.session() as session:
        version = session.get(model, version_id)
        version.passages = []
        version.text = original
        session.commit()
    offset = 0
    parts = []
    while True:
        response = client.get(url, params={"offset": offset})
        assert response.status_code == 200, response.text
        data = response.json()
        parts.append(data["plain_text"])
        assert data["pagination"]["mode"] == "text" and len(parts[-1]) <= TEXT_PAGE_SIZE
        offset = data["pagination"]["next_offset"]
        if offset is None:
            break
    assert "".join(parts) == original
    with service.db.session() as session:
        session.get(model, version_id).text = ""
        session.commit()
    data = client.get(url).json()
    assert data["pagination"]["total"] == 0 and data["plain_text"] == ""


@pytest.mark.parametrize("native", [False, True])
def test_private_page_and_bad_parameters_fail_without_evidence(harness, native):
    client, service, model, version_id, event_id, url = seed(harness, native)
    for params in (
        {"offset": -1},
        {"limit": 51},
        {"offset": 10**80},
        {"passage": "x" * 201},
        {"offset": 9999999},
    ):
        assert client.get(url, params=params).status_code == 422
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="other-page", slug="other-page", name="Other"))
        session.flush()
        if native:
            work_id = session.get(RegulatoryEvent, event_id).work_id
            session.get(RegulatoryWork, work_id).owner_organization_id = "other-page"
        else:
            session.get(Version, version_id).owner_organization_id = "other-page"
        session.commit()
    assert client.get(url, params={"passage": "p0"}).status_code == 404
