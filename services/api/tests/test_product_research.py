"""Collective research must retain evidence, revisions and workspace boundaries."""
import json
from uuid import uuid4

import httpx
import pytest
from conftest import LAW_URL
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import product_research
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry, ResearchThread


def question(client, route, title="What does the evidence establish?"):
    data = {"creation_key": str(uuid4()), "title": title, "body": "Develop a working answer using sources."}
    result = post(client, route + "/discussion", data)
    assert result.status_code == 201, result.text
    return result.json(), data


def contribution(client, path, body="The source describes the current procedure."):
    data = {"request_key": str(uuid4()), "body": body, "source_url": "https://www.fedlex.admin.ch/"}
    result = post(client, path + "/replies", data)
    assert result.status_code == 201, result.text
    return result.json(), data


def test_collective_question_replies_working_answer_and_reopening(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, data = question(client, route)
    assert post(client, route + "/discussion", data).json()["id"] == thread["id"]
    assert post(client, route + "/discussion", {**data, "body": "changed"}).status_code == 409
    path = route + "/discussion/" + thread["id"]
    reply, values = contribution(client, path)
    assert post(client, path + "/replies", values).json()["id"] == reply["id"]
    assert post(client, path + "/replies", {**values, "body": "Different contribution"}).status_code == 409
    assert post(client, path + "/accept", {"expected_revision": 1, "entry_id": reply["id"]}).status_code == 409
    result = post(client, path + "/accept", {"expected_revision": 2, "entry_id": reply["id"]})
    assert result.status_code == 200, result.text
    current = client.get(path).json()
    assert current["accepted"]["body"] == values["body"] and current["accepted"]["author"] == "Ada Example"
    assert client.get(route + "/discussion?status=open").json()["total"] == 0
    assert client.get(route).json()["discussion"] == {"questions": 1, "open_questions": 0}
    assert post(client, path + "/accept", {"expected_revision": 3, "entry_id": None}).status_code == 200
    assert client.get(path).json()["accepted"] is None
    assert client.get(route + "/discussion?status=open").json()["total"] == 1
    exported = client.get(route + "/export").json()
    assert exported["questions"][0]["id"] == thread["id"]
    assert next(e for e in exported["entries"] if e["id"] == reply["id"])["thread_id"] == thread["id"]


def test_cross_question_answers_replay_and_unsafe_source_are_denied(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    one, _ = question(client, route)
    two, _ = question(client, route, "Which source should we trust?")
    first = route + "/discussion/" + one["id"]
    second = route + "/discussion/" + two["id"]
    reply, data = contribution(client, first)
    assert post(client, second + "/accept", {"expected_revision": 1, "entry_id": reply["id"]}).status_code == 404
    assert post(client, second + "/replies", data).status_code == 409
    assert post(client, first + "/replies", {**data, "request_key": str(uuid4()), "source_url": "javascript:alert(1)"}).status_code == 422
    foreign, _ = create(client)
    assert client.get(ROOT + "/" + foreign["id"] + "/discussion/" + one["id"]).status_code == 404


def test_research_citations_are_exact_saved_snapshots_and_never_auto_accepted(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, _ = question(client, route)
    path = route + "/discussion/" + thread["id"]
    reply, _ = contribution(client, path, "An application requires a documented assessment before submission.")
    answer = {"findings": [{"claim": "A team contribution describes a required assessment.", "citations": [{"source_id": "S1", "quote": "requires a documented assessment"}]}], "unknowns": ["Verify the source's current legal status."], "search_queries": ["Swiss naturalisation assessment official"]}
    model.responses = [json.dumps(answer)]
    values = {"expected_revision": 2, "request_key": str(uuid4())}
    result = post(client, path + "/research", values)
    assert result.status_code == 200, result.text
    research = result.json()
    assert research["kind"] == "research" and research["data"]["sources"][0]["key"] == reply["id"]
    assert research["data"]["sources"][0]["kind"] == "team_contribution"
    assert len(research["data"]["sources"][0]["sha256"]) == 64
    assert client.get(path).json()["accepted"] is None
    assert post(client, path + "/research", values).json()["id"] == research["id"]
    assert len(model.calls) == 1
    assert post(client, path + "/research", {**values, "expected_revision": 3}).status_code == 409
    assert post(client, path + "/accept", {"expected_revision": 3, "entry_id": research["id"]}).status_code == 200
    brief = client.get(route + "/brief")
    assert brief.status_code == 200 and 'requires a documented assessment' in brief.text
    assert 'Verify the source' in brief.text and 'AI research note accepted by the team' in brief.text


@pytest.mark.parametrize('source,quote', [('invented', 'requires a documented assessment'), ('S1', 'A fabricated quotation not present in the source')])
def test_ai_cannot_save_invented_evidence(signed, source, quote):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, _ = question(client, route)
    path = route + "/discussion/" + thread["id"]
    contribution(client, path)
    model.responses = [json.dumps({"findings": [{"claim": "Unverified", "citations": [{"source_id": source, "quote": quote}]}], "unknowns": ["Check status"], "search_queries": ["official status"]})]
    result = post(client, path + "/research", {"expected_revision": 2, "request_key": str(uuid4())})
    assert result.status_code == 502
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == 'research')) is None
    assert client.get(path).json()['revision'] == 2


def test_changed_topic_while_ai_runs_discards_stale_research(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, _ = question(client, route)
    async def changing_model(*args, **kwargs):
        with service.db.session() as session:
            row = session.get(ResearchThread, thread['id'])
            row.revision += 1
            session.commit()
        return json.dumps({"findings": [], "unknowns": ["More evidence needed"], "search_queries": ["official procedures"]})
    model.complete = changing_model
    response = post(client, route + '/discussion/' + thread['id'] + '/research', {'expected_revision': 1, 'request_key': str(uuid4())})
    assert response.status_code == 409
    assert client.get(route + '/discussion/' + thread['id']).json()['reply_count'] == 0


def test_workspace_search_private_drafts_roles_and_product_isolation(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    private_route = ROOT + '/' + private['id']
    question(client, private_route, 'Confidential draft question about naturalisation')
    shared, _ = create(client)
    active(client, shared)
    route = ROOT + '/' + shared['id']
    thread, _ = question(client, route, 'Shared naturalisation question')
    path = route + '/discussion/' + thread['id']
    contribution(client, path, 'Naturalisation knowledge contributed by our team.')
    assert client.get('/api/products/pharma/discover?q=naturalisation').json()['items']
    assert client.get('/api/products/loyer/discover?q=naturalisation').json()['items'] == []
    reader = _register(client, 'reader@example.ch').json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader['user']['id'], organization_id=identity['organization']['id'], role='viewer'))
        session.commit()
    assert post(client, '/api/auth/session/organization', {'organization_id': identity['organization']['id']}).status_code == 200
    found = client.get('/api/products/pharma/discover?q=naturalisation').json()
    results = found['items']
    assert found['total'] == len(results) == 3
    assert results and all(item['dossier_id'] == shared['id'] for item in results)
    assert client.get(private_route+'/discussion').status_code == 404
    assert client.get(path).status_code == 200
    assert post(client, path+'/replies', {'request_key':str(uuid4()),'body':'Not authorized'}).status_code == 403
    assert post(client, path+'/accept', {'expected_revision':2,'entry_id':None}).status_code == 403
    assert post(client, path+'/research', {'expected_revision':2,'request_key':str(uuid4())}).status_code == 403
    assert client.post(path+'/replies',json={'request_key':str(uuid4()),'body':'No csrf'}).status_code == 403
    client.cookies.clear()
    assert _register(client, 'other@example.ch').status_code == 201
    foreign_search = client.get('/api/products/pharma/discover?q=naturalisation').json()
    assert foreign_search['items'] == [] and foreign_search['total'] == 0
    assert client.get(path).status_code == 404


def test_external_search_sends_only_explicit_query_to_fixed_hosts(signed, monkeypatch):
    client, _, _, _ = signed
    real_client = httpx.AsyncClient
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'GET' and 'cookie' not in request.headers
        assert 'confidential' not in str(request.url)
        if request.url.host == 'fedlex.data.admin.ch':
            assert request.headers['accept'] == 'application/sparql-results+json'
            return httpx.Response(200,json={'results':{'bindings':[{'work':{'value':'https://fedlex.data.admin.ch/eli/cc/abc'},'title':{'value':'Official result'}},{'work':{'value':'https://evil.test/x'},'title':{'value':'Reject foreign URL'}}]}})
        assert request.url.host == 'www.ebi.ac.uk'
        assert request.url.params['query'] == 'GLP-1 safety'
        return httpx.Response(200,json={'resultList':{'result':[{'source':'MED','id':'123','title':'Study result','authorString':'Authors','journalTitle':'Journal'}]}})
    monkeypatch.setattr(product_research.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw))
    doc, _ = create(client)
    post(client, ROOT+'/'+doc['id']+'/entries', {'request_key':str(uuid4()),'kind':'note','body':'confidential client information'})
    for provider, query in [('fedlex','naturalisation'),('europepmc','GLP-1 safety')]:
        response = client.get('/api/products/pharma/discover',params={'provider':provider,'q':query})
        assert response.status_code == 200, response.text
        assert len(response.json()['items']) == 1
        assert response.json()['query'] == query
    assert len(seen) == 2
    def unavailable(request):
        return httpx.Response(503)
    monkeypatch.setattr(product_research.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(unavailable),**kw))
    response = client.get('/api/products/pharma/discover?provider=fedlex&q=naturalisation')
    assert response.status_code == 503 and 'temporarily unavailable' in response.text


def test_new_saved_material_reopens_need_for_human_review(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    active(client, doc)
    route = ROOT + '/' + doc['id']
    thread, _ = question(client, route)
    path = route + '/discussion/' + thread['id']
    reply, _ = contribution(client, path)
    assert post(client, path+'/accept', {'expected_revision':2,'entry_id':reply['id']}).status_code == 200
    initial = client.get(path).json()
    assert initial['accepted_at'] and not initial['answer_needs_review']
    reference = post(client, route+'/entries', {'request_key':str(uuid4()),'kind':'reference','title':'New material','body':'A new source needs assessment.','url':LAW_URL}).json()
    changed = client.get(path).json()
    assert changed['answer_needs_review'] and changed['accepted_entry_id'] == reply['id']
    assert post(client, path+'/accept', {'expected_revision':3,'entry_id':reply['id']}).status_code == 200
    assert not client.get(path).json()['answer_needs_review']
    assert post(client, route+'/sources/'+reference['id']+'/monitor', {}).status_code == 200
    assert client.get(path).json()['answer_needs_review']
    brief = client.get(route+'/brief')
    assert 'Review needed:' in brief.text and 'New saved material' in brief.text
    assert post(client, path+'/accept', {'expected_revision':4,'entry_id':reply['id']}).status_code == 200
    assert not client.get(path).json()['answer_needs_review']
