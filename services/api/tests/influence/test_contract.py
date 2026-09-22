"""Evidence contracts run without unrelated application integrations."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from helvetic_lens.influence_contract import Document


def document():
    return {
        "id": "test-dossier",
        "title": "Synthetic evidence dossier",
        "checkedOn": "2025-04-02",
        "summaryLanguage": "en",
        "entities": [
            {
                "id": "company",
                "name": "Synthetic company",
                "kind": "company",
                "country": "CH",
                "x": 30,
                "y": 30,
            },
            {
                "id": "recipients",
                "name": "Aggregate recipients",
                "kind": "group",
                "country": None,
                "x": 360,
                "y": 30,
            },
        ],
        "sources": [
            {
                "id": "annual-report",
                "title": "Synthetic annual report",
                "publisher": "Synthetic company",
                "url": "https://example.org/report",
                "kind": "primary_corporate",
                "language": "en",
                "publishedOn": "2025-04-01",
                "checkedOn": "2025-04-02",
                "snapshotText": "In 2024 we paid CHF 2000 in dividends.",
            },
            {
                "id": "response",
                "title": "Synthetic reply",
                "publisher": "Synthetic company",
                "url": "https://example.org/reply",
                "kind": "primary_corporate",
                "language": "en",
                "publishedOn": "2025-04-02",
                "checkedOn": "2025-04-02",
            },
        ],
        "edges": [
            {
                "id": "payment",
                "from": "company",
                "to": "recipients",
                "kind": "dividend",
                "status": "documented",
                "label": "Dividend",
                "statement": "Aggregate dividend of CHF 2000 paid.",
                "asOf": "2024-12-31",
                "supporting": [
                    {
                        "sourceId": "annual-report",
                        "locator": "page 1",
                        "summary": "Recorded cash payment.",
                        "quote": "CHF 2000",
                    }
                ],
                "disputing": [],
                "limits": ["No individual allocation or country attribution."],
                "money": {
                    "amount": 2000,
                    "currency": "CHF",
                    "periodStart": "2024-01-01",
                    "periodEnd": "2024-12-31",
                    "basis": "paid",
                    "evidenceSourceId": "annual-report",
                },
            }
        ],
        "gaps": ["No personal payment record."],
    }


def save_body(value=None, revision=0):
    return {
        "document": value or document(),
        "expectedRevision": revision,
        "note": "Reviewed the synthetic evidence.",
        "requestId": str(uuid4()),
    }


def test_source_extract_and_exact_quotes_survive_contract_validation():
    result = Document.model_validate(document()).model_dump(mode="json", by_alias=True)
    assert result["edges"][0]["from"] == "company"
    assert result["sources"][0]["snapshotText"] == "In 2024 we paid CHF 2000 in dividends."


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["edges"][0].update(to="missing"),
        lambda d: d["entities"].append(deepcopy(d["entities"][0])),
        lambda d: d["edges"][0]["supporting"][0].update(sourceId="missing"),
        lambda d: d["edges"][0]["supporting"][0].update(quote="invented quotation"),
        lambda d: d["edges"][0].update(status="disputed"),
        lambda d: d["edges"][0].update(
            disputing=[{"sourceId": "response", "locator": "reply", "summary": "Denies the allegation."}]
        ),
        lambda d: d["sources"][0].update(kind="reporting"),
        lambda d: d["edges"][0].update(kind="ownership"),
        lambda d: d["edges"][0].update(kind="potential_impact", money=None),
        lambda d: d["edges"][0]["money"].update(basis="proposed"),
        lambda d: d["edges"][0]["money"].update(amount=float("nan")),
        lambda d: d["edges"][0]["money"].update(amount=-1),
        lambda d: d["edges"][0]["money"].update(periodEnd="2026-12-31"),
        lambda d: d["edges"][0]["money"].update(evidenceSourceId="response"),
        lambda d: d["sources"][0].update(url="javascript:alert(1)"),
        lambda d: d["sources"][0].update(url="https://user:secret@example.org"),
        lambda d: d["sources"][0].update(checkedOn="2099-01-01"),
        lambda d: d["sources"][0].update(publishedOn="2025-05-01"),
        lambda d: d.update(organization_id="some-other-workspace"),
    ],
)
def test_invalid_or_overstated_evidence_is_rejected(mutation):
    value = document()
    mutation(value)
    with pytest.raises(ValidationError):
        Document.model_validate(value)


def test_dispute_and_proposal_are_retained_without_promoting_them():
    value = document()
    edge = value["edges"][0]
    edge.update(
        status="disputed",
        money=None,
        kind="business",
        disputing=[{"sourceId": "response", "locator": "reply", "summary": "This is contested."}],
    )
    assert Document.model_validate(value).edges[0].status == "disputed"
    edge.update(kind="potential_impact", status="not_established")
    assert Document.model_validate(value).edges[0].status == "not_established"
