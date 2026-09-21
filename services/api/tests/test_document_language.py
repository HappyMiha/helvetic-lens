from conftest import policy

from helvetic_lens.models import Law

WORK = "https://fedlex.data.admin.ch/eli/cc/2022/491"


def test_direct_fedlex_watches_keep_requested_language_and_pinned_edition(harness):
    client, fetcher, service, _ = harness
    italian, german, historical = [WORK + suffix for suffix in ("/it", "/de", "/20250401/de")]
    for url in (italian, german, historical):
        fetcher.values[url] = policy(extra=f"<p>Synthetic fixture for {url}</p>")
    original = client.post("/api/laws", json={"url": italian}).json()
    # Simulate the pre-fix persisted work-wide identity without changing its ID.
    with service.db.session() as session:
        session.get(Law, original["id"]).canonical_identity = WORK
        session.commit()
    current = client.post("/api/laws", json={"url": german})
    assert current.status_code == 201, current.text
    assert current.json()["id"] != original["id"]
    assert current.json()["url"] == german
    pinned = client.post("/api/laws", json={"url": historical})
    assert pinned.status_code == 201, pinned.text
    assert pinned.json()["id"] not in {original["id"], current.json()["id"]}
    assert pinned.json()["url"] == historical
    calls = len(fetcher.calls)
    for suffix in ("/it", "/de", "/20250401/de"):
        response = client.post("/api/laws", json={"url": "https://www.fedlex.admin.ch/eli/cc/2022/491" + suffix})
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "duplicate_law"
    assert len(fetcher.calls) == calls
    saved = client.get("/api/laws/" + original["id"]).json()
    assert saved["url"] == italian
    assert saved["current_version_id"] == original["current_version_id"]


def test_www_alias_and_existing_private_edition_deduplicate_without_republishing(harness):
    client, fetcher, service, _ = harness
    url = "https://www.fedlex.admin.ch/eli/cc/2007/758/de"
    fetcher.values[url] = policy()
    saved = client.post("/api/laws", json={"url": url})
    assert saved.status_code == 201, saved.text
    assert saved.json()["corpus_scope"] == "shared_public"
    assert client.post("/api/laws", json={"url": url}).status_code == 409
    with service.db.session() as session:
        law = session.get(Law, saved.json()["id"])
        law.owner_organization_id = service.organization_id
        law.canonical_identity = "https://fedlex.data.admin.ch/eli/cc/2007/758"
        session.commit()
    duplicate = client.post("/api/laws", json={"url": url.replace("www.fedlex.admin.ch", "fedlex.data.admin.ch")})
    assert duplicate.status_code == 409, duplicate.text
    with service.db.session() as session:
        assert session.get(Law, saved.json()["id"]).owner_organization_id == service.organization_id
