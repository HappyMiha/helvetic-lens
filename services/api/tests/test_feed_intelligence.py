"""Semantic feed contracts with controlled model adapters, never live-provider claims."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf
from test_product_dossiers import create, post
from test_product_dossiers import signed as signed
from test_product_feeds import new_feed, observe

from helvetic_lens import decision_engines
from helvetic_lens import feed_intelligence as intelligence
from helvetic_lens.feed_assessments import next_unassessed, persist_assessment
from helvetic_lens.feed_models import Feed, FeedAssessment, FeedDossierLink, FeedUpdate
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_investigations import scope


def planned(spec):
    return {'contract': intelligence.CONTRACT, 'binding': spec['binding'], 'feed_revision': spec['feed_revision'],
        'status': 'ready', 'relevance_scope': 'Prevention of myocardial infarction and cardiovascular harm, including cardioprotection evidence; exclude commercial promotions.', 'understanding': 'Prevent cardiovascular events through relevant clinical and policy evidence.',
        'concepts': ['myocardial infarction', 'prevention'], 'synonyms': ['heart attack', 'cardioprotection'],
        'queries': [{'query': 'myocardial infarction prophylaxis clinical evidence', 'language': 'en', 'purpose': 'Find equivalent clinical terminology.'},
            {'query': 'Herzinfarkt Prävention Evidenz', 'language': 'de', 'purpose': 'Find German source terminology.'}]}


def test_precision_feedback_are_revision_bound_and_change_future_semantic_input(signed):
    client, service, _, _ = signed
    value, _ = new_feed(client)
    path = '/api/feeds/' + value['id']
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        source, _ = observe(session, feed, 1)
        source_id = source.id
        session.commit()
    command = {'request_key': str(uuid4()), 'expected_revision': value['revision'],
        'include': [' prevention of cardiovascular harm ', 'prevention of cardiovascular harm'],
        'exclude': ['Product advertising'], 'languages': ['en', 'de']}
    refined = client.patch(path + '/intelligence', headers=_csrf(client), json=command)
    assert refined.status_code == 200, refined.text
    assert refined.json()['revision'] == value['revision'] + 1
    assert refined.json()['intelligence']['include'] == ['prevention of cardiovascular harm']
    assert client.patch(path + '/intelligence', headers=_csrf(client), json=command).json()['revision'] == refined.json()['revision']
    assert client.patch(path + '/intelligence', headers=_csrf(client), json={**command, 'request_key': str(uuid4())}).status_code == 409
    feedback = {'request_key': str(uuid4()), 'expected_revision': refined.json()['revision'],
        'verdict': 'not_relevant', 'reason': 'This is an advertising campaign, not prevention evidence.'}
    marked = post(client, path + '/updates/' + source_id + '/feedback', feedback)
    assert marked.status_code == 200 and marked.json()['intelligence']['feedback_count'] == 1
    assert post(client, path + '/updates/' + source_id + '/feedback', feedback).json()['revision'] == marked.json()['revision']
    with service.db.session() as session:
        spec = intelligence.spec(session, session.get(Feed, value['id']))
        assert spec['exclude'] == ['Product advertising']
        assert spec['feedback'][0]['verdict'] == 'not_relevant'
        assert 'advertising campaign' in spec['feedback'][0]['reason']
        assert 'cached_plan' not in spec
    shown = client.get(path + '/updates').json()['items'][0]
    assert shown['feedback'] == 'not_relevant' and shown['relevance']['verdict'] == 'pending'


@pytest.mark.asyncio
async def test_query_plan_uses_configured_gateway_multilingual_concepts_and_no_lexical_fallback(signed, monkeypatch):
    client, service, _, model = signed
    value, _ = new_feed(client, query='heart attack prevention')
    with service.db.session() as session:
        spec = intelligence.spec(session, session.get(Feed, value['id']))
    calls = []

    async def complete(system, user, **kwargs):
        calls.append((system, json.loads(user), kwargs['response_schema']))
        return json.dumps({key: value for key, value in planned(spec).items()
            if key in {'understanding', 'relevance_scope', 'concepts', 'synonyms', 'queries'}})

    monkeypatch.setattr(model, 'complete', complete)
    result = await intelligence.prepare(service, spec)
    assert result['status'] == 'ready' and intelligence.cached(spec, result)
    assert calls[0][2]['title'] == 'SemanticPlan'
    assert calls[0][1]['query'] == 'heart attack prevention'
    assert 'myocardial infarction' in result['queries'][0]['query']
    assert {q['language'] for q in result['queries']} == {'en', 'de'}
    assert not intelligence.cached({**spec, 'feed_revision': spec['feed_revision'] + 1}, result)

    async def unavailable(*args, **kwargs):
        raise RuntimeError('SECRET_PROVIDER_BODY')

    monkeypatch.setattr(model, 'complete', unavailable)
    failed = await intelligence.prepare(service, spec)
    assert failed['status'] == 'unavailable' and failed['queries'] == []
    assert 'SECRET_PROVIDER_BODY' not in str(failed)


@pytest.mark.asyncio
async def test_laya_relevance_uses_meaning_feedback_and_never_substitutes_keyword_match(signed, monkeypatch):
    client, service, _, _ = signed
    value, _ = new_feed(client, query='heart attack prevention')
    with service.db.session() as session:
        spec = intelligence.spec(session, session.get(Feed, value['id']))
    spec['exclude'] = ['commercial promotions']
    calls = []

    class Laya:
        async def choose(self, state, instructions, criteria):
            calls.append((state, instructions, criteria))
            return decision_engines.Decision('laya', 'local-semantic-fixture', 'relevant',
                {'relevant': .9, 'uncertain': .08, 'unrelated': .02}, .9, .9, 4, 100, 1)

    monkeypatch.setattr(decision_engines, 'engines', lambda settings: {'laya': Laya()})
    item = {'title': 'Clinical evidence', 'url': 'https://example.org/research',
        'source_text': 'Cardioprotection reduces myocardial infarction incidence.'}
    result = await intelligence.evaluate(service.settings, spec, planned(spec), item)
    assert result['verdict'] == 'relevant' and result['engine'] == 'laya'
    assert calls[0][0]['source_text'] == item['source_text']
    assert 'commercial promotions' in calls[0][2]['relevant']
    assert 'Disagreement does not imply irrelevance' in calls[0][1]
    too_large = await intelligence.evaluate(service.settings, spec, planned(spec), {**item, 'source_text': 'X' * 4001})
    assert too_large['verdict'] == 'unavailable' and len(calls) == 1

    class Down:
        async def choose(self, *args):
            raise decision_engines.DecisionUnavailable('not_configured')

    monkeypatch.setattr(decision_engines, 'engines', lambda settings: {'laya': Down()})
    missing = await intelligence.evaluate(service.settings, spec, planned(spec), {**item, 'source_text': spec['query']})
    assert missing['verdict'] == 'unavailable' and missing['engine'] is None


def test_assessments_append_without_new_body_versions_and_server_filters_archive(signed):
    client, service, _, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        first, _ = observe(session, feed, 1)
        second, _ = observe(session, feed, 2)
        third, _ = observe(session, feed, 3)
        spec = intelligence.spec(session, feed)
        plan = planned(spec)
        decision = {'verdict': 'unrelated', 'engine': 'laya', 'scope': 'Every original portion was assessed.', 'portions': []}
        saved = persist_assessment(session, feed, first, spec, plan, decision)
        assert persist_assessment(session, feed, first, spec, plan, decision).id == saved.id
        persist_assessment(session, feed, second, spec, plan, {'verdict': 'uncertain', 'engine': 'laya', 'portions': []})
        persist_assessment(session, feed, third, spec, plan, {'verdict': 'unavailable', 'engine': None, 'portions': []})
        assert next_unassessed(session, feed, spec).id == third.id
        persist_assessment(session, feed, third, spec, plan, {'verdict': 'relevant', 'engine': 'laya', 'portions': []})
        assert next_unassessed(session, feed, spec) is None
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 3
        assert session.scalar(select(func.count()).select_from(FeedAssessment)) == 4
        session.commit()
    path = '/api/feeds/' + value['id'] + '/updates'
    main = client.get(path + '?view=main&order=newest&limit=1').json()
    assert main['total'] == 2 and main['total_retained'] == 3
    assert main['items'][0]['relevance']['verdict'] == 'relevant'
    older = client.get(path, params={'view': 'main', 'order': 'newest', 'before_sequence': main['next_sequence']}).json()
    assert len(older['items']) == 1 and older['items'][0]['relevance']['verdict'] == 'uncertain'
    archive = client.get(path + '?view=unrelated').json()
    assert archive['total'] == 1 and archive['items'][0]['relevance']['verdict'] == 'unrelated'
    assert client.get(path + '?view=all').json()['total'] == 3
    changed = client.patch('/api/feeds/' + value['id'] + '/intelligence', headers=_csrf(client), json={
        'request_key': str(uuid4()), 'expected_revision': value['revision'], 'include': ['A new research relationship'], 'exclude': []})
    assert changed.status_code == 200
    # Old decisions are retained, but cannot silently classify a changed semantic scope.
    fresh = client.get(path + '?view=main').json()
    assert fresh['total'] == 3 and all(row['relevance']['verdict'] == 'pending' for row in fresh['items'])


def test_public_dossier_preview_apply_and_revocation_pin_exclude_private_notes(signed, monkeypatch):
    from helvetic_lens import product_exploration
    from helvetic_lens.product_models import DossierEntry

    client, service, identity, _ = signed
    value, _ = new_feed(client)
    doc, _ = create(client)
    path = f'/api/products/pharma/dossiers/{doc["id"]}/feeds'
    attached = post(client, path, {'request_key': str(uuid4()), 'feed_id': value['id'],
        'expected_feed_revision': value['revision'], 'question': 'Which public safety changes matter?'}).json()
    with service.db.session() as session:
        run = Investigation(dossier_id=doc['id'], actor_user_id=identity['user']['id'],
            created_by_user_id=identity['user']['id'], request_key=str(uuid4()),
            question='Which public safety changes matter?', external_discovery=True, status='completed')
        session.add(run)
        session.flush()
        source = InvestigationSource(**scope(run), source_key='a' * 64, kind='public_source', title='Public record',
            url='https://example.org/source', sha256='b' * 64, snapshot={'excerpts': [{'text': 'The public source records a changed condition.', 'passage': 'p1'}]})
        session.add(source)
        session.add(DossierEntry(dossier_id=doc['id'], request_key=str(uuid4()), actor_user_id=identity['user']['id'],
            kind='comment', title='Private comment', body='SECRET_CLIENT_NOTE_MUST_NEVER_TRAIN_SEARCH'))
        session.flush()
        source_id, run_id = source.id, run.id
        session.commit()
    projection = {'status': 'ready', 'briefing': {'findings': [{'statement': 'The public condition changed.',
        'source_id': source_id, 'quote': 'The public source records a changed condition.', 'locator': 'p1'}],
        'uncertainties': ['The reason for the public change is unresolved.']}}
    monkeypatch.setattr(product_exploration, 'projection', lambda session, run: projection)
    target = path + '/' + attached['id'] + '/learn'
    preview = client.get(target)
    assert preview.status_code == 200, preview.text
    context = preview.json()
    assert context['findings'][0]['source_id'] == source_id and 'SECRET_CLIENT_NOTE' not in str(context)
    applied = post(client, target, {'request_key': str(uuid4()), 'expected_feed_revision': value['revision'],
        'expected_link_revision': attached['revision'], 'context_fingerprint': context['context_fingerprint']})
    assert applied.status_code == 200, applied.text
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        spec = intelligence.spec(session, feed)
        assert spec['dossier_context'][0]['investigation_id'] == run_id
        assert 'SECRET_CLIENT_NOTE' not in str(spec)
        old = spec['binding']
        link = session.get(FeedDossierLink, attached['id'])
        link.status, link.revision = 'detached', link.revision + 1
        session.flush()
        revoked = intelligence.spec(session, feed)
        assert revoked['dossier_context'] == [] and revoked['context_unavailable']
        assert revoked['binding'] != old
        shown = intelligence.projection(session, feed)
        assert shown['context_count'] == 0 and shown['context_unavailable_count'] == 1


@pytest.mark.asyncio
async def test_exact_laya_request_bounds_cover_unicode_escaping_and_every_original_character(signed, monkeypatch):
    from pydantic import SecretStr

    client, service, _, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        spec = intelligence.spec(session, session.get(Feed, value['id']))
    plan = planned(spec)
    plan['relevance_scope'] = ('Українське право та статус захисту; ' * 40)[:1200]
    original = ('контекст😀\"\t\n' * 1200)
    item = {'title': 'Українське право ' * 30, 'source_text': original}
    requests = []

    async def bounded(url, key, body, **kwargs):
        requests.append(body)
        assert len(str(body['state'])) <= 4000  # Actual installed laya.serve limit.
        assert len(json.dumps(body, ensure_ascii=False).encode('utf-8')) <= 20000
        assert set(body['state']) == {'source_text'}
        assert plan['relevance_scope'] in body['questions']['decision']['criteria']['relevant']
        return {'model': 'controlled-local-model', 'answers': {'decision': {'type': 'choice',
            'choice': 'uncertain', 'probabilities': {'relevant': .1, 'uncertain': .8, 'unrelated': .1}, 'confidence': .8}}}

    monkeypatch.setattr(decision_engines, 'bounded_json', bounded)
    configuration = service.settings.model_copy(update={'laya_base_url': 'http://127.0.0.1:8000/v1/systemone',
        'laya_api_key': SecretStr('controlled-test-key')})
    offset = 0
    while offset < len(original):
        size = intelligence.gate_characters(spec, plan, item, original[offset:])
        assert 0 < size <= intelligence.GATE_CHARACTERS
        portion = original[offset:offset + size]
        result = await intelligence.evaluate(configuration, spec, plan, {**item, 'source_text': portion})
        assert result['verdict'] == 'uncertain' and result['evaluated_characters'] == size
        offset += size
    assert ''.join(body['state']['source_text'] for body in requests) == original
    assert len(requests) > 1
    assert not intelligence.cached(spec, {**plan, 'relevance_scope': ''})


def test_watch_changes_proposal_creates_context_with_one_explicit_action_and_no_model_on_read(signed, monkeypatch):
    from helvetic_lens import product_exploration
    from helvetic_lens.product_models import ProductDossier

    client, service, identity, model = signed
    doc, _ = create(client)
    path = f'/api/products/pharma/dossiers/{doc["id"]}/feeds'
    first = client.get(path + '/proposal')
    assert first.status_code == 200, first.text
    assert first.json()['basis'] == 'question_only' and first.json()['findings'] == []
    assert model.calls == []
    with monkeypatch.context() as guest:
        from helvetic_lens import feed_api
        guest.setattr(feed_api, 'organization_member', lambda *args: None)
        assert client.get(path + '/proposal').status_code == 403
    body = {'request_key': str(uuid4()), 'name': first.json()['name'], 'query': first.json()['query'],
        'question': first.json()['question'], 'sources': [], 'status': 'paused',
        'proposal_fingerprint': first.json()['proposal_fingerprint']}
    with service.db.session() as session:
        parent = session.get(ProductDossier, doc['id'])
        parent.revision += 1
        session.commit()
    assert post(client, path + '/create', body).status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Feed)) == 0
    refreshed = client.get(path + '/proposal').json()
    simple = post(client, path + '/create', {**body, 'proposal_fingerprint': refreshed['proposal_fingerprint']})
    assert simple.status_code == 201, simple.text
    with service.db.session() as session:
        assert intelligence.settings(session.get(Feed, simple.json()['feed_id']))['contexts'] == []
        run = Investigation(dossier_id=doc['id'], actor_user_id=identity['user']['id'],
            created_by_user_id=identity['user']['id'], request_key=str(uuid4()),
            question='Which public safety changes affect the published framework?', external_discovery=True, status='completed')
        session.add(run)
        session.flush()
        source = InvestigationSource(**scope(run), source_key='c' * 64, kind='public_source', title='Public record',
            url='https://example.org/public', sha256='d' * 64,
            snapshot={'excerpts': [{'text': 'A public safety condition changed.', 'passage': 'p1'}]})
        session.add(source)
        session.flush()
        source_id, run_id = source.id, run.id
        session.commit()
    monkeypatch.setattr(product_exploration, 'projection', lambda session, run: {'status': 'ready',
        'briefing': {'findings': [{'statement': 'The safety condition changed.', 'source_id': source_id,
            'quote': 'A public safety condition changed.', 'locator': 'p1'}],
            'uncertainties': ['Which cases are affected?']}})
    preview = client.get(path + '/proposal').json()
    assert preview['basis'] == 'public_research' and preview['findings'][0]['source_id'] == source_id
    assert preview['gaps'] == ['Which cases are affected?'] and model.calls == []
    command = {'request_key': str(uuid4()), 'name': 'Edited watch name',
        'query': 'Track changed conditions and their practical meaning.', 'question': preview['question'],
        'sources': [], 'status': 'paused', 'proposal_fingerprint': preview['proposal_fingerprint']}
    enabled = post(client, path + '/create', command)
    assert enabled.status_code == 201, enabled.text
    assert post(client, path + '/create', command).json()['id'] == enabled.json()['id']
    with service.db.session() as session:
        feed = session.get(Feed, enabled.json()['feed_id'])
        current = intelligence.spec(session, feed)
        assert current['query'] == command['query']
        assert current['dossier_context'][0]['investigation_id'] == run_id
        assert current['dossier_context'][0]['findings'][0]['source_id'] == source_id
        assert session.scalar(select(func.count()).select_from(Feed)) == 2
        # An otherwise-public run containing private inputs cannot export derived findings/gaps.
        session.add(InvestigationSource(**scope(session.get(Investigation, run_id)),
            source_key='e' * 64, kind='file', title='Private file', url='', sha256='f' * 64,
            snapshot={'text': 'SECRET_PRIVATE_INPUT'}))
        session.flush()
        parent = session.get(ProductDossier, doc['id'])
        mixed = intelligence.public_context(session, parent)
        assert mixed['findings'] == [] and mixed['gaps'] == []
        revoked = intelligence.spec(session, feed)
        assert revoked['dossier_context'] == [] and revoked['context_unavailable']
