"""Official dated JOLux relation resources identify a parent work, not a new law."""
import pytest
import test_fedlex_connector as fixture

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.fedlex_connector import FedlexConnector, _eli_collection

PARENT = "https://fedlex.data.admin.ch/eli/cc/2022/172"
DATED = PARENT + "/20260919"


@pytest.mark.parametrize("language", ["de", "fr", "it"])
@pytest.mark.asyncio
async def test_rss_relations_retain_dated_reference_and_bind_parent_work(monkeypatch, language):
    rows = [{"relation": fixture.binding(fixture.WORK), "relationClass": fixture.binding("basicAct"),
             "fromWork": fixture.binding(fixture.WORK), "toWork": fixture.binding(DATED)}]
    monkeypatch.setattr(fixture, "relation_rows", lambda: rows)
    connector = FedlexConnector(Settings(_env_file=None), language=language, transport=fixture.fedlex_transport())
    page = await connector.discover_since(None, {})
    metadata = await connector.fetch_metadata(page.items[0])
    relations = await connector.extract_relations(metadata)
    assert len(relations) == 1
    relation = relations[0]
    assert relation.target.stable_official_url == PARENT
    assert relation.target.identifiers[0].value == PARENT
    assert relation.target.metadata["relation_resource_uri"] == DATED
    assert relation.target.metadata["relation_version_token"] == "20260919"
    assert relation.evidence["to_work"] == DATED
    assert relation.state == "confirmed" and relation.provenance_method == "official_metadata"
    assert relation.target.dates == ()
    # This exception is only for a verified relation field, not root discovery.
    with pytest.raises(DomainError):
        _eli_collection(DATED)


@pytest.mark.asyncio
async def test_version_to_own_parent_is_not_an_inter_work_relation(monkeypatch):
    rows = [{"relation": fixture.binding(fixture.WORK), "relationClass": fixture.binding("basicAct"),
             "fromWork": fixture.binding(fixture.WORK), "toWork": fixture.binding(fixture.WORK + "/20260919")}]
    monkeypatch.setattr(fixture, "relation_rows", lambda: rows)
    connector = FedlexConnector(Settings(_env_file=None), transport=fixture.fedlex_transport())
    page = await connector.discover_since(None, {})
    metadata = await connector.fetch_metadata(page.items[0])
    assert await connector.extract_relations(metadata) == ()


@pytest.mark.parametrize("url", [
    DATED.replace("fedlex.data.admin.ch", "unrelated.example"),
    PARENT + "/20261319", PARENT + "/20260230", PARENT + "/2026091",
    DATED + "/de", DATED + "/de/html", DATED + "?version=other",
])
def test_relation_resource_does_not_weaken_publisher_or_identity_boundaries(url):
    with pytest.raises(DomainError):
        FedlexConnector._target_document(url)


def test_numeric_root_identifier_is_not_mistaken_for_a_version_date():
    url = "https://fedlex.data.admin.ch/eli/cc/2022/12345678"
    result = FedlexConnector._target_document(url)
    assert result.stable_official_url == url
    assert "relation_version_token" not in result.metadata
