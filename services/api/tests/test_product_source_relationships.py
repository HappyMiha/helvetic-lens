"""Captured provenance must not become independent support or legal validity."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_claim_evolution import FIRST, SECOND, fixture
from test_product_dossiers import signed as signed
from test_product_investigations import complete

from helvetic_lens.product_investigation_models import ClaimChange, ClaimEvidence, InvestigationSource
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.product_source_relationships import VERSION, compare


def evidence(*, url="https://example.org/report", digest="a" * 64, kind="public_source", quote="A retained source quotation."):
    return {"quote": quote, "source": {"url": url, "sha256": digest, "kind": kind,
        "captured_at": "2026-09-28T12:00:00+00:00"}}


@pytest.mark.parametrize("url", ["https://mirror.example/report", "https://example.org/report#page-2"])
def test_matching_captures_never_become_independent_confirmation(url):
    old, new = evidence(), evidence(url=url)
    result = compare(old, new)
    assert result["relationship"] == "matching_captured_content"
    assert result["content_hash_match"] is True
    assert result["same_supporting_excerpt"] is True
    assert result["source_independence"] == "not_established"
    assert result["policy_version"] == VERSION
    assert "repeated evidence" in result["basis"]
    assert "complete-document" in result["basis"]


@pytest.mark.parametrize("url,same", [
    ("https://example.org/report#different-section", True),
    ("https://example.org/report?edition=2", False),
    ("https://example.org/other", False),
    ("http://example.org/report", False),
    ("https://example.org/Report", False),
])
def test_source_address_matching_is_conservative_and_dates_are_observations(url, same):
    old, new = evidence(), evidence(url=url, digest="b" * 64)
    new["source"]["captured_at"] = "2026-09-29T12:00:00+00:00"
    result = compare(old, new)
    assert result["same_recorded_address"] is same
    assert result["relationship"] == ("same_recorded_address" if same else "unestablished")
    assert result["content_hash_match"] is False
    assert result["same_supporting_excerpt"] is True  # Same quote is not document equivalence.
    assert result["observed_at"]["previous"] != result["observed_at"]["current"]
    assert result["publication_and_effective_dates"] == "not_established_by_capture_metadata"
    assert result["source_independence"] == "not_established"


@pytest.mark.parametrize("changes", [
    {"sha256": ""}, {"sha256": "not-a-digest"}, {"sha256": "x" * 64},
    {"kind": "uploaded_file"}, {"kind": ""},
])
def test_missing_or_incomparable_capture_hashes_remain_unknown(changes):
    old, new = evidence(url=""), evidence(url="")
    new["source"].update(changes)
    result = compare(old, new)
    assert result["content_hash_match"] is None
    assert result["relationship"] == "unestablished"
    assert result["source_independence"] == "not_established"


@pytest.mark.parametrize("url", ["", "file:///tmp/evidence", "https://user:secret@example.org/report", "https://[invalid", "https://example.org:bad/report", "https://example.org/a\nreport"])
def test_invalid_addresses_and_missing_evidence_do_not_establish_source_identity(url):
    result = compare(evidence(url=url), evidence(url=url, digest="b" * 64))
    assert result["same_recorded_address"] is None
    assert result["relationship"] == "unestablished"
    assert compare(None, None)["same_supporting_excerpt"] is None


@pytest.mark.parametrize("product", ["pharma", "legal"])
@pytest.mark.parametrize("public", [False, True])
def test_source_pair_provenance_reaches_existing_reader_and_obeys_withdrawal(signed, monkeypatch, product, public):
    client, service, doc, root, runs, first, submit, calls, _, _ = fixture(
        signed, monkeypatch, product="loyer" if product == "legal" else product,
        public=public, kind="CORROBORATES")
    # The Legal API alias retains the existing storage identity. Exercise the
    # current public product route without inventing new stored product values.
    root, runs = root.replace("/loyer/", "/legal/"), runs.replace("/loyer/", "/legal/")
    second = complete(client, service, runs, submit(FIRST))
    # Two actual saved fixture runs have the same submitted content. Assign their
    # synthetic origin addresses to represent a mirror; never fetch these URLs.
    with service.db.session() as session:
        link = session.scalar(select(ClaimChange))
        old = session.get(InvestigationSource, session.get(ClaimEvidence, link.previous_evidence_id).source_id)
        new = session.get(InvestigationSource, session.get(ClaimEvidence, link.evidence_id).source_id)
        old.url, new.url = "https://example.org/original", "https://mirror.example/copy"
        assert old.sha256 == new.sha256
        retained = {"kind": link.kind, "status": link.status, "history": deepcopy(link.history), "revision": link.revision}
        session.commit()
    if public:
        client.cookies.clear()
    before_calls = len(calls)
    response = client.get(root + "/evidence-changes")
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    item = response.json()["items"][0]
    assert {k: item[k] for k in retained} == retained
    assert item["source_relationship"]["relationship"] == "matching_captured_content"
    assert item["source_relationship"]["same_recorded_address"] is False
    assert item["source_relationship"]["source_independence"] == "not_established"
    assert "repeated evidence" in item["basis"] and "effective dates" in item["basis"]
    assert item["previous"]["evidence"]["quote"] == item["current"]["evidence"]["quote"] == FIRST
    assert item["previous"]["investigation_id"] == first["id"]
    assert item["current"]["investigation_id"] == second["id"]
    assert len(calls) == before_calls  # Reader/provenance performs no inference.
    if not public:
        assert client.get(root + "/export").json()["evidence_changes"] == [item]
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", url="https://example.org/original",
            request_key=str(uuid4()), body="PRIVATE EXCLUSION REASON", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    hidden = client.get(root + "/evidence-changes?status=all")
    assert hidden.json()["items"] == [] and hidden.json()["total"] == 0
    assert "source_relationship" not in hidden.text and "PRIVATE EXCLUSION" not in hidden.text


def test_changed_capture_at_one_address_preserves_temporal_comparison_and_reviews(signed, monkeypatch):
    from test_product_dossiers import post

    client, service, _, root, runs, _, submit, _, _, _ = fixture(signed, monkeypatch)
    complete(client, service, runs, submit(SECOND))
    with service.db.session() as session:
        link = session.scalar(select(ClaimChange))
        for identifier in (link.previous_evidence_id, link.evidence_id):
            source = session.get(InvestigationSource, session.get(ClaimEvidence, identifier).source_id)
            source.url = "https://example.org/retained-record"
        session.commit()
    item = client.get(root + "/evidence-changes").json()["items"][0]
    assert item["kind"] == "UPDATES"  # Annotation never rewrites the saved relation.
    relation = item["source_relationship"]
    assert relation["relationship"] == "same_recorded_address" and relation["content_hash_match"] is False
    assert relation["same_supporting_excerpt"] is False
    assert "saved content differs" in item["basis"]
    body = {"request_key": str(uuid4()), "expected_revision": 1, "status": "dismissed",
        "reason": "The source observation date is not the effective date."}
    route = root + "/evidence-changes/" + item["id"] + "/review"
    review = post(client, route, body)
    assert review.status_code == 200 and review.json()["source_relationship"] == relation
    assert post(client, route, body).json() == review.json()
    assert review.json()["history"][0]["reason"] == body["reason"]
