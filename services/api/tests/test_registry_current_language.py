"""A current watched translation must not inherit an older edition's language."""
import pytest
from conftest import add_law, policy
from sqlalchemy import select

from helvetic_lens.models import Law, LegacyDocumentMapping, Organization, RegulatoryExpression, Version


def translated_watch(client, fetcher, service, index=0):
    url = f"https://official.example/de/leaflet-{index}"
    text = "Інформація для українців про соціальну допомогу, навчання дітей і роботу в кантоні Берн. " * 4
    fetcher.values[url] = f"<html><head><title>Пам’ятка для українців</title></head><body><main><h1>Пам’ятка для українців</h1><p>{text}</p></main></body></html>".encode()
    law = add_law(client, url=url, name=f"Ukraine leaflet {index}")
    with service.db.session() as session:
        mapping = session.scalar(select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"]))
        session.add(RegulatoryExpression(work_id=mapping.work_id, language="de", expression_key="old-edition"))
        session.commit()
        return law, mapping.work_id


def test_current_ukrainian_artifact_controls_label_and_filter_without_rewriting_history(harness):
    client, fetcher, service, model = harness
    law, work_id = translated_watch(client, fetcher, service)
    calls = len(fetcher.calls)
    selected = client.get("/api/registry", params={"view": "monitored", "language": "uk"}).json()
    assert len(selected["items"]) == 1
    assert selected["items"][0]["law_id"] == law["id"]
    assert selected["items"][0]["languages"] == ["uk"]
    assert client.get("/api/registry", params={"view": "monitored", "language": "de"}).json()["items"] == []
    assert client.get("/api/registry", params={"view": "monitored", "q": "uk"}).json()["items"][0]["law_id"] == law["id"]
    with service.db.session() as session:
        assert set(session.scalars(select(RegulatoryExpression.language).where(RegulatoryExpression.work_id == work_id))) == {"de", "uk"}
    assert len(fetcher.calls) == calls and model.calls == []


@pytest.mark.parametrize("language", [None, "", "und", "unknown"])
def test_unknown_current_language_preserves_historical_language_fallback(harness, language):
    client, fetcher, service, _ = harness
    law, _ = translated_watch(client, fetcher, service)
    with service.db.session() as session:
        version = session.get(Version, law["current_version_id"])
        version.identity_json = {**version.identity_json, "language": language}
        session.commit()
    item = client.get("/api/registry", params={"view": "monitored", "language": "de"}).json()["items"][0]
    assert item["law_id"] == law["id"] and item["languages"] == ["de", "uk"]


@pytest.mark.parametrize("wrong_binding", ["different_law", "different_owner"])
def test_current_language_does_not_read_an_inaccessible_or_unbound_version(harness, wrong_binding):
    client, fetcher, service, _ = harness
    url = "https://official.example/de/law"
    fetcher.values[url] = policy()
    law = add_law(client, url=url)
    other, _ = translated_watch(client, fetcher, service)
    with service.db.session(include_all_organizations=True) as session:
        if wrong_binding == "different_law":
            session.get(Law, law["id"]).current_version_id = other["current_version_id"]
        else:
            organization = Organization(name="Unrelated workspace", slug="unrelated-language")
            session.add(organization)
            session.flush()
            version = session.get(Version, law["current_version_id"])
            version.owner_organization_id = organization.id
            version.identity_json = {**version.identity_json, "language": "uk"}
        session.commit()
    items = client.get("/api/registry", params={"view": "monitored", "language": "uk"}).json()["items"]
    assert [item["law_id"] for item in items] == [other["id"]]


def test_current_language_filter_keyset_keeps_every_selected_watch_once(harness):
    client, fetcher, service, _ = harness
    expected = {translated_watch(client, fetcher, service, index)[0]["id"] for index in range(4)}
    cursor, seen = "", []
    for _ in range(4):
        page = client.get("/api/registry", params={"view": "monitored", "language": "uk", "limit": 1, "cursor": cursor}).json()
        seen.extend(item["law_id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert not cursor and len(seen) == len(set(seen)) == 4 and set(seen) == expected
