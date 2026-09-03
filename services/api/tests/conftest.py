"""Deterministic doubles live only in tests; the app never substitutes a model."""

import json
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.extraction import Fetched, within_section
from helvetic_lens.main import create_app

LAW_URL = "https://regulator.example/laws/retention.html"
LIST_URL = "https://regulator.example/laws/"


def policy(days=30, extra=""):
    return (
        "<html><head><title>Synthetic retention policy</title></head>"
        "<body><nav>Changing navigation is not evidence.</nav><main>"
        "<h1>Synthetic retention policy</h1>"
        f"<p>Demo organisations must retain records for {days} days.</p>"
        "<p>This fictional policy is test data and is not a legal requirement.</p>"
        f"{extra}</main><footer>Footer updated every day</footer></body></html>"
    ).encode()


@dataclass
class FakeFetcher:
    values: dict = field(
        default_factory=lambda: {
            LAW_URL: policy(),
            LIST_URL: (
                b"<html><main><h1>Example regulator documents</h1>"
                b"<p>Choose the document you want to track from this synthetic listing.</p>"
                b'<a href="retention.html">Retention policy</a>'
                b'<a href="retention.html#article">Duplicate anchor</a>'
                b'<a href="/other">Outside selected section</a>'
                b'<a href="https://other.example/laws/test">External host</a></main></html>'
            ),
        }
    )
    calls: list = field(default_factory=list)

    async def fetch(self, url, provider="native", *, boundary=None):
        if boundary and not within_section(url, *boundary):
            raise DomainError("Outside the selected section.", 422, "outside_section")
        self.calls.append((url, provider))
        value = self.values.get(url, DomainError("Source is unavailable.", 422, "source_unavailable"))
        if isinstance(value, Exception):
            raise value
        mime = "application/pdf" if value.startswith(b"%PDF") else "text/html"
        return Fetched(url, value, mime, {"provider": provider, "test_double": True})


@dataclass
class ScriptedModel:
    calls: list = field(default_factory=list)
    fail: bool = False
    invalid: bool = False
    unsupported: bool = False
    invalid_json_responses: int = 0
    unsupported_responses: int = 0

    async def complete(self, system, user, **kwargs):
        if kwargs.get("budget") is not None:
            kwargs["budget"].claim()
        self.calls.append((system, user))
        if self.fail:
            raise DomainError("Test model timed out.", 504, "model_timeout")
        if self.invalid_json_responses:
            self.invalid_json_responses -= 1
            return "{not valid JSON"
        data = json.loads(user)
        task = data.get("task")
        if task == "impact_synthesis":
            return json.dumps(
                {
                    "summary": "Test-only summary.",
                    "impact": "medium",
                    "reason": "Test-only reason.",
                    "business_areas": ["Operations"],
                    "actions": [
                        {
                            "text": "Review the changed passage.",
                            "citation_numbers": [1],
                        }
                    ],
                    "citation_numbers": [1],
                }
            )
        if task == "answer_synthesis":
            unsupported = self.unsupported or self.unsupported_responses > 0
            if self.unsupported_responses:
                self.unsupported_responses -= 1
            return json.dumps(
                {
                    "supported": not unsupported,
                    "answer": "Test-only answer."
                    if not unsupported
                    else "Not supported by this evidence.",
                    "citation_numbers": [] if unsupported else [1],
                }
            )
        supplied_evidence = data["evidence"]
        if isinstance(supplied_evidence, dict):
            columns = supplied_evidence["columns"]
            passages = [dict(zip(columns, row, strict=True)) for row in supplied_evidence["rows"]]
            for passage_item in passages:
                passage_item["version_id"] = supplied_evidence["version_ids"][passage_item["side"]]
        else:
            passages = supplied_evidence
        passage = next((p for p in passages if p["side"] == "new"), passages[0])
        citation = {
            "version_id": passage["version_id"],
            "passage_id": "invented" if self.invalid else passage["passage_id"],
            "quote": passage["text"][:80],
        }
        if task == "impact_batch":
            if kwargs.get("response_schema", {}).get("title") == "LocalImpactSignal":
                return json.dumps({"citation_rows": [1], "impact": "medium"})
            return json.dumps(
                {
                    "summary": "Test-only batch summary.",
                    "impact": "medium",
                    "reason": "Test-only batch reason.",
                    "business_areas": ["Operations"],
                    "citation_rows": [1],
                }
            )
        if task == "answer_batch":
            unsupported = self.unsupported or self.unsupported_responses > 0
            if self.unsupported_responses:
                self.unsupported_responses -= 1
            if kwargs.get("response_schema", {}).get("title") == "LocalAnswerSignal":
                return json.dumps(
                    {
                        "citation_rows": [] if unsupported else [1],
                        "supported": not unsupported,
                    }
                )
            return json.dumps(
                {
                    "supported": not unsupported,
                    "answer": "Test-only batch answer."
                    if not unsupported
                    else "Not supported by this evidence.",
                    "citation_rows": [] if unsupported else [1],
                }
            )
        if "question" in data:
            unsupported = self.unsupported or self.unsupported_responses > 0
            if self.unsupported_responses:
                self.unsupported_responses -= 1
            return json.dumps(
                {
                    "supported": not unsupported,
                    "answer": "Test-only answer."
                    if not unsupported
                    else "Not supported by this evidence.",
                    "citations": [] if unsupported else [citation],
                }
            )
        return json.dumps(
            {
                "summary": "Test-only summary.",
                "impact": "medium",
                "reason": "Test-only reason.",
                "business_areas": ["Operations"],
                "actions": [{"text": "Review the changed passage.", "citations": [citation]}],
                "citations": [citation],
            }
        )


@pytest.fixture
def harness(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "test.db").as_posix(),
        data_dir=tmp_path / "artifacts-data",
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
        allow_private_sources=False,
    )
    fetcher, model = FakeFetcher(), ScriptedModel()
    app = create_app(settings, fetcher=fetcher, model_client=model)
    with TestClient(app) as client:
        yield client, fetcher, app.state.service, model


def add_law(client, url=LAW_URL, **values):
    response = client.post("/api/laws", json={"url": url, "synthetic": True, **values})
    assert response.status_code == 201, response.text
    return response.json()


def import_old(client, law_id, body=None, **values):
    response = client.post(
        "/api/laws/" + law_id + "/import",
        files={"file": ("previous.html", body or policy(10), "text/html")},
        data={"synthetic": "true", "declared_date": "2025-01-01", **values},
    )
    assert response.status_code == 200, response.text
    return response.json()


def run_scan(client, ids, baseline=None):
    response = client.post("/api/scans", json={"law_ids": ids, "baseline_version_id": baseline})
    assert response.status_code == 202, response.text
    return client.get("/api/scans/" + response.json()["id"]).json()
