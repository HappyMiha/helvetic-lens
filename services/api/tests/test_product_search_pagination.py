"""Explicit public pages retain the exact query and never invent source completeness."""
import json
from uuid import uuid4

import httpx
import pytest
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import product_research
from helvetic_lens.product_pagination import next_cursor


def mock_source(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(product_research.httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def search(client, **values):
    return client.get("/api/products/pharma/discover", params={"q": "GLP-1 safety", "provider": "europepmc", **values})


def record(identifier):
    return {"source": "MED", "id": str(identifier), "title": f"Evidence {identifier}"}


def test_europe_pmc_two_pages_real_total_fixed_host_no_private_context(signed, monkeypatch):
    client, _, _, _ = signed
    doc, _ = create(client)
    post(client, ROOT + "/" + doc["id"] + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "confidential team context"})
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == "www.ebi.ac.uk" and request.url.path.endswith("/rest/search")
        assert request.url.params["query"] == "GLP-1 safety" and request.url.params["pageSize"] == "20"
        assert "cookie" not in request.headers and "confidential" not in str(request.url)
        if request.url.params["cursorMark"] == "*":
            return httpx.Response(200, json={"hitCount": 21, "nextCursorMark": "next+mark/==", "nextPageUrl": "https://evil.test/ignore",
                "resultList": {"result": [record(i) for i in range(20)]}})
        assert request.url.params["cursorMark"] == "next+mark/=="
        return httpx.Response(200, json={"hitCount": 21, "resultList": {"result": [record(20)]}})
    mock_source(monkeypatch, handler)
    first = search(client).json()
    assert first["total"] == 21 and first["page_number"] == 1 and len(first["items"]) == 20
    second = search(client, cursor=first["next_cursor"])
    assert second.status_code == 200, second.text
    second = second.json()
    assert second["total"] == 21 and second["page_number"] == 2 and second["items"][0]["id"] == "MED:20"
    assert second["next_cursor"] is None and not second["continuation_unavailable"] and len(seen) == 2


def test_fedlex_grouped_ordered_lookahead_pages_leave_total_unknown(signed, monkeypatch):
    client, _, _, _ = signed
    queries = []
    def handler(request):
        assert request.url.host == "fedlex.data.admin.ch"
        query = request.url.params["query"]
        queries.append(query)
        assert 'MIN(STR(?label))' in query and 'GROUP BY ?work ORDER BY STR(?work) LIMIT 21' in query
        assert json.dumps('act "quoted"') in query
        start, end = (0, 21) if "OFFSET 0" in query else (20, 22)
        rows = [{"work": {"value": f"https://fedlex.data.admin.ch/eli/cc/{i:03}"}, "title": {"value": f"Act {i}"}} for i in range(start, end)]
        return httpx.Response(200, json={"results": {"bindings": rows}})
    mock_source(monkeypatch, handler)
    first = search(client, provider="fedlex", q='Act "quoted"').json()
    assert len(first["items"]) == 20 and first["total"] is None and first["next_cursor"]
    second = search(client, provider="fedlex", q='Act "quoted"', cursor=first["next_cursor"]).json()
    assert len(second["items"]) == 2 and second["total"] is None and second["next_cursor"] is None
    assert {r["id"] for r in first["items"]}.isdisjoint(r["id"] for r in second["items"])
    assert "OFFSET 20" in queries[1]


@pytest.mark.parametrize("group", [0, 1])
def test_cursor_validation_rejects_mismatch_bounds_and_workspace_before_network(signed, monkeypatch, group):
    client, _, _, _ = signed
    def unexpected(request):
        raise AssertionError("Invalid continuation must not request a provider")
    mock_source(monkeypatch, unexpected)
    good = next_cursor("europepmc", "GLP-1 safety", 20, "next")
    invalid = ({"cursor": "A"}, {"cursor": "!"}, {"cursor": "x" * 2049}, {"cursor": good, "q": "different terms"},
                   {"cursor": good, "provider": "fedlex"}, {"cursor": good, "provider": "workspace"},
                   {"cursor": next_cursor("europepmc", "GLP-1 safety", 1000, "next")},
                   {"cursor": next_cursor("europepmc", "GLP-1 safety", 21, "next")},
                   {"cursor": next_cursor("europepmc", "GLP-1 safety", True, "next")},
                   {"cursor": next_cursor("europepmc", "GLP-1 safety", 20, "https://evil.test/")})
    # Each fixture stays within the existing six-request discovery rate budget.
    for values in invalid[group * 5:(group + 1) * 5]:
        assert search(client, **values).status_code == 422


@pytest.mark.parametrize("body", [{}, {"resultList": {"result": "invalid"}},
    {"hitCount": "unknown", "resultList": {"result": []}},
    {"nextCursorMark": "https://evil.test/", "resultList": {"result": [record(1)]}}])
def test_malformed_provider_payloads_are_unavailable_not_empty_success(signed, monkeypatch, body):
    client, _, _, _ = signed
    mock_source(monkeypatch, lambda request: httpx.Response(200, json=body))
    assert search(client).status_code == 503


def test_empty_final_repeated_missing_and_capped_continuation_states(signed, monkeypatch):
    client, _, _, _ = signed
    body = {"hitCount": 0, "nextCursorMark": "*", "resultList": {"result": []}}
    mock_source(monkeypatch, lambda request: httpx.Response(200, json=body))
    empty = search(client).json()
    assert empty["total"] == 0 and empty["items"] == [] and empty["next_cursor"] is None
    body.update(hitCount=20, nextCursorMark="next", resultList={"result": [record(i) for i in range(20)]})
    complete = search(client).json()
    assert complete["next_cursor"] is None and not complete["limit_reached"] and not complete["continuation_unavailable"]
    body.update(hitCount=30, nextCursorMark="same", resultList={"result": [record(1)]})
    repeated = search(client, cursor=next_cursor("europepmc", "GLP-1 safety", 20, "same")).json()
    assert repeated["next_cursor"] is None and repeated["continuation_unavailable"]
    body.pop("nextCursorMark")
    assert search(client).json()["continuation_unavailable"]
    body.update(hitCount=1020, nextCursorMark="next", resultList={"result": [record(i) for i in range(20)]})
    capped = search(client, cursor=next_cursor("europepmc", "GLP-1 safety", 980, "previous")).json()
    assert capped["page_number"] == 50 and capped["limit_reached"] and capped["next_cursor"] is None


def test_page_failure_remains_retriable_and_unknown_count_is_not_zero(signed, monkeypatch):
    client, _, _, _ = signed
    calls = []
    def handler(request):
        calls.append(request.url.params["cursorMark"])
        if len(calls) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"nextCursorMark": "next" if len(calls) == 1 else None, "resultList": {"result": [record(1)]}})
    mock_source(monkeypatch, handler)
    first = search(client).json()
    assert first["total"] is None and first["next_cursor"]
    assert search(client, cursor=first["next_cursor"]).status_code == 503
    assert search(client, cursor=first["next_cursor"]).status_code == 200
    assert calls == ["*", "next", "next"]
