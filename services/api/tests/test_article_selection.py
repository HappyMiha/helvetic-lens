"""Retained official fixture; all modified source revisions are synthetic tests."""

import hashlib
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from conftest import run_scan
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings

from helvetic_lens.article_selection import comparison_projection, extract_document
from helvetic_lens.config import DomainError
from helvetic_lens.diffing import DIFF_SCHEMA_VERSION, compare_passages
from helvetic_lens.extraction import Fetched, extract
from helvetic_lens.main import create_app
from helvetic_lens.models import Comparison, Version

URL = "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de"
ARTIFACT = "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/27/317_321_377/20260101/de/html/retained-test-fixture.html"
BODY = (Path(__file__).parent / "fixtures/fedlex-or-20260101-range.html").read_bytes()
METADATA = {
    "fedlex_eli": True, "eli_language": "de", "eli_format": "html",
    "eli_work_uri": "https://fedlex.data.admin.ch/eli/cc/27/317_321_377",
    "eli_expression_uri": "https://fedlex.data.admin.ch/eli/cc/27/317_321_377/20260101/de",
    "eli_version_date": "2026-01-01", "eli_title": "Obligationenrecht (OR), SR 220",
}
SELECTION = {"start": "319", "end": "323b", "language": "de"}
NUMBERS = ["319", "320", "321", "321a", "321b", "321c", "321d", "321e", "322", "322a", "322b", "322c", "322d", "323", "323a", "323b"]


class ArticleFetcher:
    body = BODY

    async def fetch(self, url, provider="native", *, boundary=None):
        if isinstance(self.body, Exception):
            raise self.body
        return Fetched(ARTIFACT, self.body, "text/html", METADATA)


def parsed(body=BODY, selection=None):
    return extract_document(Fetched(ARTIFACT, body, "text/html", METADATA), "or.html",
                            selection=selection or SELECTION, source_url=URL)


def create(client, **extra):
    response = client.post("/api/laws", json={"url": URL, "article_selection": SELECTION, **extra})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def selected_harness(harness):
    client, _, service, model = harness
    fetcher = ArticleFetcher()
    service.fetcher = fetcher
    return client, fetcher, service, model


def test_retained_official_articles_are_complete_ordered_and_include_lettered_boundaries():
    document = parsed()
    assert [p["article_number"] for p in document.passages] == NUMBERS
    assert "Art. 318\n" not in document.text and "Art. 324\n" not in document.text
    assert "2 Endigt das Arbeitsverhältnis" in document.passages[12]["text"]
    assert "wenn es verabredet ist." in document.passages[12]["text"]
    assert "Gratifikation" in document.passages[12]["article_heading"]
    assert document.selection_provenance["scope"] == "Art. 319–323b OR, DE"
    assert document.selection_provenance["official_version_date"] == "2026-01-01"
    assert document.selection_provenance["original_sha256"] == hashlib.sha256(BODY).hexdigest()
    # Every normative source paragraph/list is present in the selected text.
    source = BeautifulSoup(BODY, "html.parser")
    for passage in document.passages:
        article = source.find(id=passage["source_anchor"])
        for node in article.select(".collapseable p, .collapseable li"):
            assert " ".join(node.get_text(" ", strip=True).split()) in passage["text"]


def test_limit_applies_after_selection_but_whole_document_still_has_limit():
    large = BODY.replace(b'<main id="maintext">', b'<main id="maintext"><p>' + b"outside " * 170000 + b"</p>")
    with pytest.raises(DomainError, match="MVP text limit"):
        extract(large, "text/html")
    assert parsed(large).content_hash == parsed().content_hash
    with pytest.raises(DomainError, match="input limit"):
        parsed(b"x" * (8 * 1024 * 1024 + 1))


@pytest.mark.parametrize("change", ["missing_start", "missing_end", "missing_middle", "duplicate", "toc_only", "wrong_heading", "empty_body", "unsupported_number"])
def test_ambiguous_or_incomplete_structure_is_never_a_success(change):
    soup = BeautifulSoup(BODY, "html.parser")
    if change.startswith("missing_"):
        soup.find(id={"missing_start": "art_319", "missing_end": "art_323_b", "missing_middle": "art_322"}[change]).decompose()
    elif change == "duplicate":
        soup.select_one("#maintext").append(BeautifulSoup(str(soup.find(id="art_322")), "html.parser"))
    elif change == "toc_only":
        soup.select_one("#maintext").decompose()
        soup.body.append(BeautifulSoup('<nav>Art. 319 Art. 322d Art. 323b</nav>', "html.parser"))
    elif change == "wrong_heading":
        soup.find(id="art_322_d").select_one("h6 a").string = "Art. 324"
    elif change == "empty_body":
        soup.find(id="art_322_d").select_one(".collapseable").clear()
    else:
        soup.find(id="art_322_d")["id"] = "art_322_d_bis"
    with pytest.raises(DomainError):
        parsed(str(soup).encode())


@pytest.mark.parametrize("selection", [
    {"start": "323b", "end": "319"}, {"start": "322d", "end": "322a"},
    {"start": "0", "end": "319"}, {"start": "319junk", "end": "323b"},
    {"start": "319", "end": "323b", "language": "fr"},
])
def test_invalid_ranges_fail_before_fetch(selected_harness, selection):
    client, fetcher, _, _ = selected_harness
    fetcher.body = AssertionError("invalid input must not fetch")
    response = client.post("/api/preview", json={"url": URL, "article_selection": selection})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_article_range"


def test_natural_order_single_article_and_source_restrictions(selected_harness):
    client, _, _, _ = selected_harness
    assert [p["article_number"] for p in parsed(selection={"start": "322", "end": "322d"}).passages] == ["322", "322a", "322b", "322c", "322d"]
    assert len(parsed(selection={"start": "322d", "end": "322d"}).passages) == 1
    for url, provider in [(URL[:-2] + "fr", "native"), (URL, "firecrawl"), ("https://example.org/law", "native"), (URL + "/pdf-a", "native")]:
        response = client.post("/api/preview", json={"url": url, "provider": provider, "article_selection": SELECTION})
        assert response.status_code == 422


def test_preview_saved_scope_dates_evidence_and_repeat_scan(selected_harness):
    client, _, _, _ = selected_harness
    preview = client.post("/api/preview", json={"url": URL, "article_selection": SELECTION}).json()
    assert len(preview["selection_provenance"]["articles"]) == 16
    assert "Art. 323b" in preview["excerpt"]
    law = create(client, preview_content_hash=preview["content_hash"])
    detail = client.get(f"/api/laws/{law['id']}?paged_history=true").json()
    assert detail["article_selection"] == SELECTION
    current = detail["current_version"]
    assert current["declared_date"] == "2026-01-01" and current["date_provenance"] == "fedlex"
    assert current["created_at"][:10] != current["declared_date"]
    evidence = client.get(f"/api/versions/{current['id']}/page?passage=art-322d").json()
    assert evidence["pagination"]["target_found"]
    assert evidence["selection_provenance"]["scope"] == "Art. 319–323b OR, DE"
    assert client.get(evidence["artifact_url"]).content == BODY
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "unchanged"
    assert client.get(f"/api/laws/{law['id']}").json()["current_version_id"] == current["id"]


def test_inside_and_outside_synthetic_changes_and_failure_preserve_evidence(selected_harness):
    client, fetcher, _, _ = selected_harness
    law = create(client)
    soup = BeautifulSoup(BODY, "html.parser")
    soup.find(id="art_324").select_one("p").append(" Synthetic outside-range modification.")
    fetcher.body = str(soup).encode()
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "unchanged"
    soup.find(id="art_322_d").select_one("p").append(" Synthetic inside-range modification.")
    fetcher.body = str(soup).encode()
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "changed"
    saved = client.get(f"/api/laws/{law['id']}").json()
    good_id = saved["current_version_id"]
    assert good_id != law["current_version_id"]
    # An interior lettered article disappearing must also stop the scan.
    soup.find(id="art_321_c").decompose()
    for damaged in [str(soup).encode(), BODY.replace(b'art_323_b', b'missing_323_b'), DomainError("Temporary fetch failure")]:
        fetcher.body = damaged
        assert run_scan(client, [law["id"]])["items"][0]["result"] == "failed"
        detail = client.get(f"/api/laws/{law['id']}").json()
        assert detail["current_version_id"] == good_id
        assert len(detail["versions"]) == 2
        assert detail["last_error"]


def test_changed_preview_and_distinct_range_histories(selected_harness):
    client, _, _, _ = selected_harness
    rejected = client.post("/api/laws", json={"url": URL, "article_selection": SELECTION, "preview_content_hash": "0" * 64})
    assert rejected.status_code == 409
    first = create(client)
    second = create(client, article_selection={"start": "322", "end": "322d"})
    assert first["id"] != second["id"]
    assert first["current_version_id"] != second["current_version_id"]
    assert client.patch(f"/api/laws/{first['id']}", json={"article_selection": {"start": "322", "end": "322d"}}).status_code == 422
    assert client.post("/api/laws", json={"url": URL, "article_selection": SELECTION}).status_code == 409
    assert client.post(f"/api/laws/{first['id']}/import", data={"text": "A partial unstructured article cannot replace the range."}).status_code == 422
    contexts = [client.post(f"/api/laws/{law['id']}/question-context").json()["comparison_id"] for law in (first, second)]
    assert contexts[0] != contexts[1]


def test_first_version_real_ask_pipeline_citations_cache_and_no_fake_change(selected_harness):
    client, _, service, model = selected_harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = create(client)
    context = client.post(f"/api/laws/{law['id']}/question-context")
    assert context.status_code == 200, context.text
    comparison_id = context.json()["comparison_id"]
    detail = client.get(f"/api/laws/{law['id']}").json()
    assert detail["comparison_id"] is None and detail["comparisons"] == []
    assert not any(item.get("kind") == "comparison" for item in detail["regulatory_timeline"]["timeline"])
    question = {"question": "Welche Bedeutung haben Art. 319, 322 und 322d OR für einen virtuellen VSOP? Unterscheide Gesetzestext und Einordnung.", "output_locale": "de-CH"}
    response = client.post(f"/api/comparisons/{comparison_id}/ask", json=question)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["supported"] and result["citations"] and model.calls
    system, user = model.calls[-1]
    supplied = json.loads(user)
    assert "Art. 319–323b OR, DE" in user
    assert "Art. 322d" in user and "Art. 324\\n" not in user
    assert "Art. 320\\n" not in user and "Art. 321a\\n" not in user
    assert result["coverage"]["included_passages"] == 3
    assert "interpretation" in system and "case law" in system
    for citation in result["citations"]:
        assert citation["version_id"] == law["current_version_id"]
        evidence = client.get(f"/api/versions/{citation['version_id']}/page?passage={citation['passage_id']}").json()
        assert any(citation["quote"] in p["text"] for p in evidence["passages"])
        assert citation["url"].startswith("/evidence/")
    assert supplied["document_context"]["old_version"]["id"] == supplied["document_context"]["new_version"]["id"]
    assert result["coverage"]["available_passages"] == 16
    count = len(model.calls)
    assert client.post(f"/api/comparisons/{comparison_id}/ask", json=question).json()["cached"]
    assert len(model.calls) == count
    model.unsupported = True
    response = client.post(f"/api/comparisons/{comparison_id}/ask", json={"question": "Welche Rechtsprechung fehlt zur Verfallklausel?"})
    assert response.status_code == 200 and not response.json()["supported"]


def test_snapshot_followup_bounds_history_and_preserves_local_evidence_rules(selected_harness):
    client, _, service, model = selected_harness
    service.settings.apertus_provider = "docker"
    law = create(client)
    comparison = client.post(f"/api/laws/{law['id']}/question-context").json()["comparison_id"]
    history = [{"question": "Demo-Fall: VSOP ohne Vertrag. " * 40,
                "answer": "Previous interpretation is untrusted. " * 100,
                "citations": [{"version_id": law["current_version_id"], "passage_id": "art-319",
                               "quote": "Never duplicate this saved quote in conversation hints."}]}
               for _ in range(4)]
    response = client.post(f"/api/comparisons/{comparison}/ask", json={
        "question": "Welche Bedeutung haben Art. 319, 322 und 322d OR?", "history": history,
        "output_locale": "de-CH",
    })
    assert response.status_code == 200, response.text
    assert response.json()["response_mode"] == "selected_evidence"
    system, user = model.calls[-1]
    context = json.loads(user)
    assert len(context["previous_questions"]) == 2
    assert len(json.dumps(context["previous_questions"])) < 2300
    assert "Never duplicate" not in user
    assert "case law" in system and "only one saved snapshot" in system
    assert all(f"Art. {number}\\n" in user for number in ("319", "322", "322d"))
    # Retained conversation remains complete despite its bounded inference hints.
    saved = client.get(f"/api/comparisons/{comparison}/ai-history").json()
    retained = next(item for item in saved["items"] if item["type"] == "question")["history"]
    assert len(retained) == 4
    assert retained[0]["question"] == history[0]["question"].strip()
    assert retained[0]["answer"] == history[0]["answer"].strip()
    assert retained[0]["citations"][0]["quote"] == history[0]["citations"][0]["quote"]
    model.unsupported = True
    response = client.post(f"/api/comparisons/{comparison}/ask", json={
        "question": "Welche Rechtsprechung gilt für einen VSOP?", "output_locale": "de-CH",
    })
    assert not response.json()["supported"]
    assert "wurden nicht geprüft" in response.json()["answer"]
    assert "geänderten Passagen" not in response.json()["answer"]


def test_feature_available_to_two_organizations_with_private_evidence_and_questions(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=ArticleFetcher())
    with TestClient(app) as first, TestClient(app) as second:
        assert _register(first, "range-one@example.ch").status_code == 201
        assert _register(second, "range-two@example.ch").status_code == 201
        laws = []
        for client in (first, second):
            response = client.post("/api/laws", json={"url": URL, "article_selection": SELECTION}, headers=_csrf(client))
            assert response.status_code == 201, response.text
            laws.append(response.json())
        assert laws[0]["id"] != laws[1]["id"]
        context = first.post(f"/api/laws/{laws[0]['id']}/question-context", headers=_csrf(first))
        assert context.status_code == 200
        for path in [f"/api/laws/{laws[0]['id']}", f"/api/versions/{laws[0]['current_version_id']}/page",
                     f"/api/comparisons/{context.json()['comparison_id']}/ai-history"]:
            assert second.get(path).status_code == 404
        assert second.post(f"/api/laws/{laws[0]['id']}/question-context", headers=_csrf(second)).status_code == 404


def test_unknown_official_date_and_invalid_citation_are_not_fabricated(selected_harness, monkeypatch):
    client, _, service, model = selected_harness
    monkeypatch.setitem(METADATA, "eli_version_date", None)
    law = create(client)
    assert law["current_version"]["declared_date"] is None
    assert law["current_version"]["date_provenance"] is None
    assert law["current_version"]["selection_provenance"]["official_version_date"] is None
    service.settings.apertus_base_url = "https://model.example/v1"
    model.invalid = True
    context = client.post(f"/api/laws/{law['id']}/question-context").json()
    response = client.post(f"/api/comparisons/{context['comparison_id']}/ask", json={"question": "Explain Art. 322d."})
    assert response.status_code >= 400
    assert "invented" not in response.text


def editorial_revision(*, substantive=None, unpaired=False):
    soup = BeautifulSoup(BODY, "html.parser")
    article = soup.find(id="art_322_a")
    note = article.select_one(".footnotes p[id]")
    for link in article.select("sup a"):
        link.string = "114"
    if unpaired:
        note.select_one("a")["href"] = "#missing-back-reference"
    # Adjacent inline spans render the same word without added spaces.
    wording = article.select("p.absatz")[-1].select_one("span")
    wording.replace_with(BeautifulSoup(str(wording).replace("Erfolgsrechnung", "Erfolgsrec</span><span>h</span><span>nung"), "html.parser"))
    if substantive == "paragraph_number":
        article.select("p.absatz")[-1].select_one("sup").string = "4"
    elif substantive == "effective_year":
        text = note.find(string=lambda value: value and "2013" in value)
        text.replace_with(text.replace("2013", "2014"))
    elif substantive == "right":
        text = article.find(string=lambda value: value and "nötigen Aufschlüsse" in value)
        text.replace_with(text.replace("nötigen Aufschlüsse", "vollständigen Aufschlüsse"))
    return str(soup).encode()


def test_source_confirmed_footnotes_and_inline_layout_preserve_evidence():
    changed = editorial_revision()
    old, new = parsed().passages, parsed(changed).passages
    retained = json.dumps([old, new], ensure_ascii=False)
    assert compare_passages(old, new)["material_count"] == 1
    diff = compare_passages(comparison_projection(old, BODY), comparison_projection(new, changed))
    assert diff["material_count"] == 0
    assert diff["classification_counts"]["formatting"] == 1
    assert diff["counts"] == {"added": 0, "removed": 0, "modified": 1, "unchanged": 15}
    assert json.dumps([old, new], ensure_ascii=False) == retained
    assert "120" in old[9]["text"] and "114" in new[9]["text"]


@pytest.mark.parametrize("change", ["paragraph_number", "effective_year", "right"])
def test_editorial_projection_never_hides_changed_legal_numbers_or_wording(change):
    changed = editorial_revision(substantive=change)
    diff = compare_passages(comparison_projection(parsed().passages, BODY),
                            comparison_projection(parsed(changed).passages, changed))
    assert diff["material_count"] == 1
    assert diff["classification_counts"]["substantive"] == 1


def test_unpaired_footnote_is_not_silently_discarded():
    changed = editorial_revision(unpaired=True)
    projected = comparison_projection(parsed(changed).passages, changed)
    assert "editorial_comparison_key" not in projected[9]
    assert compare_passages(comparison_projection(parsed().passages, BODY), projected)["material_count"] == 1


def test_saved_article_comparison_upgrade_preserves_versions_and_originals(selected_harness):
    client, fetcher, service, _ = selected_harness
    law = create(client)
    old_id = law["current_version_id"]
    fetcher.body = editorial_revision()
    item = run_scan(client, [law["id"]])["items"][0]
    comparison_id = item["comparison_id"]
    with service.db.session() as session:
        record = session.get(Comparison, comparison_id)
        before = [(version.id, version.content_hash, version.text, version.passages, version.artifact_key)
                  for version in (session.get(Version, old_id), session.get(Version, record.new_version_id))]
        # Simulate a stored projection produced by the previous release.
        record.diff = {**record.diff, "schema_version": DIFF_SCHEMA_VERSION - 1, "material_count": 1}
        session.commit()
    response = client.get(f"/api/comparisons/{comparison_id}")
    assert response.status_code == 200, response.text
    assert response.json()["diff"]["schema_version"] == DIFF_SCHEMA_VERSION
    assert response.json()["diff"]["material_count"] == 0
    assert response.json()["old_version"]["date_provenance"] == "fedlex"
    with service.db.session() as session:
        for version_id, digest, text, passages, key in before:
            version = session.get(Version, version_id)
            assert (version.content_hash, version.text, version.passages, version.artifact_key) == (digest, text, passages, key)
            artifact = (service.settings.storage_path / "artifacts" / key).read_bytes()
            assert hashlib.sha256(artifact).hexdigest() == version.selection_provenance["original_sha256"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_article_comparison_stops_when_original_is_missing_or_corrupt(selected_harness, corrupt):
    client, _, service, _ = selected_harness
    law = create(client)
    context = client.post(f"/api/laws/{law['id']}/question-context").json()
    with service.db.session() as session:
        record = session.get(Comparison, context["comparison_id"])
        record.diff = {**record.diff, "schema_version": DIFF_SCHEMA_VERSION - 1}
        version = session.get(Version, law["current_version_id"])
        saved_text = version.text
        artifact = service.settings.storage_path / "artifacts" / version.artifact_key
        session.commit()
    if corrupt:
        artifact.write_bytes(BODY + b"<!-- altered -->")
    else:
        artifact.unlink()
    response = client.get(f"/api/comparisons/{context['comparison_id']}")
    assert response.status_code == 409
    assert response.json()["code"] == ("comparison_original_integrity" if corrupt else "comparison_original_unavailable")
    with service.db.session() as session:
        assert session.get(Version, law["current_version_id"]).text == saved_text
        assert session.get(Comparison, context["comparison_id"]).diff["schema_version"] == DIFF_SCHEMA_VERSION - 1
