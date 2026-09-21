"""Guidance has source continuity; dates, contents and cited laws are not its identity."""
import pytest
from conftest import add_law, run_scan
from sqlalchemy import func, select

from helvetic_lens.identity import assess_document_identity
from helvetic_lens.models import IdentityDecision, Observation, Version


@pytest.mark.parametrize(("title", "lines", "expected_title"), [
    ("Hauptnavigation", ["Ukraine", "Schutzstatus S", "Inhalt aktualisiert", "14.09.2026"], None),
    ("Weisung III. Asylbereich - 6. Rechtliche Stellung", ["6.1", "6.1.2", "6.2"],
     "Weisung III. Asylbereich - 6. Rechtliche Stellung"),
    ("unterstuetzungsrichtlinien-wsu-2026.pdf",
     ["Departement für Wirtschaft, Soziales und Umwelt Basel-Stadt", "Unterstützungsrichtlinien",
      "gültig ab 1. Januar 2026", "Inhaltsverzeichnis", "3.2.2", "Im Rahmen von Art. 12 BV Unterstützte"],
     "Unterstützungsrichtlinien"),
    ("Faktenblatt «Schutzstatus S»",
     ["Staatssekretariat für Migration SEM", "Faktenblatt «Schutzstatus S»",
      "Der Schutzstatus S ist seit der Totalrevision im Gesetz geregelt."], "Faktenblatt «Schutzstatus S»"),
    ("merkblatt-sozialhilfe-status-s-de.pdf",
     ["Gesundheits-, Sozial- und Integrationsdirektion", "4. Mai 2022",
      "Sozialhilfe für Personen mit Status S im Kanton Bern",
      "in Gesetz über die Sozialhilfe im Asyl- und Flüchtlingsbereich"],
     "Sozialhilfe für Personen mit Status S im Kanton Bern"),
])
def test_guidance_title_and_source_are_not_replaced_by_contents_or_citations(title, lines, expected_title):
    url = "https://official.example/guidance"
    args = dict(law_name="Довідкова інформація для українців", law_url=url, title=title,
                source_url=url, passages=[{"text": line} for line in lines])
    report = assess_document_identity(**args)
    assert report["status"] == "probable"
    assert report["reason_code"] == "watched_page_continuity"
    assert report["detected_identifier"] is None
    assert report["artifact"]["official_identifiers"] == []
    if expected_title:
        assert report["detected_title"] == expected_title
    # An unrelated source cannot establish continuity for an opaque assignment.
    moved = assess_document_identity(**{**args, "source_url": url + "/other"})
    assert moved["status"] == "unknown"


@pytest.mark.parametrize("label", ["SR 142.20", "RS 142.20"])
def test_explicit_official_identifier_still_blocks_a_conflicting_work(label):
    result = assess_document_identity(
        law_name="SR 910.13 Landwirtschaft", law_url="https://official.example/document",
        title="Faktenblatt Status S", source_url="https://official.example/document",
        passages=[{"text": label}, {"text": "6.1.2"}],
    )
    assert result["status"] == "mismatch"
    assert result["reason_code"] == "official_sr_mismatch"
    assert result["detected_identifier"] == "sr:142.20"


def test_daily_scan_refreshes_legacy_false_identity_without_replacing_saved_evidence(harness):
    client, fetcher, service, model = harness
    url = "https://official.example/guidance"
    fetcher.values[url] = b"<html><head><title>Faktenblatt Status S</title></head><body><main><h1>Faktenblatt Status S</h1><p>Informationen zu Arbeit und Integration im Kanton.</p><p>14.09.2026</p></main></body></html>"
    law = add_law(client, url=url, name="Довідкова інформація для українців")
    version_id = law["current_version_id"]
    with service.db.session() as session:
        version = session.get(Version, version_id)
        before = (version.content_hash, version.extractor, version.passages)
        old_identity = {**version.identity_json, "revision": "artifact-identity-v2",
                        "canonical_work_id": "sr:14.09.2026",
                        "official_identifiers": [{"scheme": "SR/RS", "value": "14.09.2026"}]}
        version.identity_json = old_identity
        observations = session.scalar(select(func.count()).select_from(Observation))
        session.commit()
    scan = run_scan(client, [law["id"]])
    assert scan["items"][0]["result"] == "unchanged"
    with service.db.session() as session:
        version = session.get(Version, version_id)
        assert version.identity_json["revision"] == "artifact-identity-v3"
        assert version.identity_json["canonical_work_id"] is None
        assert before == (version.content_hash, version.extractor, version.passages)
        assert session.scalar(select(func.count()).select_from(Version)) == 1
        assert session.scalar(select(func.count()).select_from(Observation)) == observations + 1
        assert session.scalar(select(func.count()).select_from(IdentityDecision)) == 0
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == version_id
    assert model.calls == []


def test_law_cover_before_a_guidance_reference_still_blocks_wrong_assignment():
    url = "https://official.example/guidance"
    result = assess_document_identity(
        law_name="Довідкова інформація для українців", law_url=url,
        title="document.pdf", source_url=url,
        passages=[{"text": "Verordnung über die Direktzahlungen an die Landwirtschaft"},
                  {"text": "Merkblatt zur Verwendung der Formulare"}],
    )
    assert result["status"] == "mismatch"
    assert result["detected_title"].startswith("Verordnung")
