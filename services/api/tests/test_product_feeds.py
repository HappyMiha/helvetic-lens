"""Standalone feed ownership, immutable history and explicit complete dossier admission."""
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf, _register
from test_product_dossiers import create, post
from test_product_dossiers import signed as signed

from helvetic_lens import feed_research
from helvetic_lens.config import DomainError
from helvetic_lens.feed_models import Feed, FeedDossierLink, FeedImport
from helvetic_lens.feed_operations import record_update
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_document_storage import retain
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_models import DossierAllowanceSlot, ProductDossier


def new_feed(client, **changes):
    body = {"request_key": str(uuid4()), "name": "Source changes", "query": "What changed in the published framework?",
        "product": "legal", "sources": [], "status": "paused", **changes}
    result = post(client, '/api/feeds', body)
    assert result.status_code == 201, result.text
    return result.json(), body


def observe(session, feed, number, *, url=None, text=None, snapshot=None):
    text = text or f"Original publisher observation number {number}. Conditions and exceptions remain part of the source."
    return record_update(session, feed, title=f"Source {number}", url=url or f"https://example.org/source/{number}",
        summary="Publisher preview", source_text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
        snapshot_json=snapshot or {"reading_complete": False}, published_at="2026-10-14")


def test_standalone_no_dossier_allowance_exact_replay_and_ownership(signed):
    client, service, _, model = signed
    feed, body = new_feed(client)
    assert post(client, '/api/feeds', body).json()['id'] == feed['id']
    assert post(client, '/api/feeds', {**body, 'query': 'A different question altogether'}).status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(ProductDossier)) == 0
        assert session.scalar(select(func.count()).select_from(DossierAllowanceSlot)) == 0
    assert client.get('/api/feeds').json()['total'] == 1
    assert client.get('/api/feeds?q=published').json()['total'] == 1
    assert client.get('/api/feeds?q=NO_SUCH_FEED').json()['total'] == 0
    assert client.get('/api/feeds?q=%25').json()['total'] == 0
    assert model.calls == []
    assert client.post('/api/feeds', json={**body, 'request_key': str(uuid4())}).status_code == 403
    assert _register(client, 'other-feed-owner@example.ch', 'Other workspace').status_code == 201
    assert client.get('/api/feeds/' + feed['id']).status_code == 404
    assert client.get('/api/feeds/' + feed['id'] + '/updates').status_code == 404
    assert client.get('/api/feeds').json()['total'] == 0


def test_noop_change_stale_save_and_current_viewer_cannot_mutate(signed):
    client, service, identity, _ = signed
    feed, body = new_feed(client)
    path = '/api/feeds/' + feed['id']
    command = {key: body[key] for key in ('name', 'query', 'sources', 'status')}
    command.update(request_key=str(uuid4()), expected_revision=feed['revision'])
    unchanged = client.patch(path, headers=_csrf(client), json=command)
    assert unchanged.status_code == 200 and unchanged.json()['revision'] == feed['revision']
    changed = client.patch(path, headers=_csrf(client), json={**command, 'request_key': str(uuid4()), 'name': 'Changed title'})
    assert changed.status_code == 200 and changed.json()['revision'] == feed['revision'] + 1
    assert client.patch(path, headers=_csrf(client), json={**command, 'request_key': str(uuid4())}).status_code == 409
    assert client.patch(path, headers=_csrf(client), json=command).json()['name'] == 'Changed title'
    with service.db.session() as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity['user']['id']))
        member.role = 'viewer'
        session.commit()
    assert client.get(path).json()['can_manage'] is False
    assert client.patch(path, headers=_csrf(client), json=command).status_code == 403


def test_immutable_changes_preserve_return_to_previous_body_and_paginate_every_version(signed):
    client, service, _, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        first, created = observe(session, feed, 1, url='https://example.org/changing', text='Version A')
        repeated, duplicated = observe(session, feed, 2, url=first.url, text='Version A')
        second, _ = observe(session, feed, 2, url=first.url, text='Version B')
        third, _ = observe(session, feed, 3, url=first.url, text='Version A')
        assert created and not duplicated and repeated.id == first.id
        assert [first.sequence, second.sequence, third.sequence] == [1, 2, 3]
        for i in range(4, 124):
            observe(session, feed, i)
        session.commit()
    path = '/api/feeds/' + value['id'] + '/updates'
    seen, cursor = [], 0
    while True:
        page = client.get(path, params={'after_sequence': cursor, 'limit': 50}).json()
        seen.extend(item['sequence'] for item in page['items'])
        if page['next_sequence'] is None:
            break
        cursor = page['next_sequence']
    assert page['total'] == 123 and seen == list(range(1, 124))
    recent = client.get(path, params={'order': 'newest', 'limit': 50}).json()
    assert [item['sequence'] for item in recent['items']] == list(range(123, 73, -1))
    older = client.get(path, params={'order': 'newest', 'before_sequence': recent['next_sequence'], 'limit': 100}).json()
    assert [item['sequence'] for item in older['items']] == list(range(73, 0, -1))
    assert older['next_sequence'] is None and older['total'] == 123
    assert 'artifact_key' not in str(page)
    assert client.get('/api/feeds/' + value['id']).json()['unread_count'] == 123


def test_create_dossier_admits_all_history_future_updates_and_shared_quota(signed):
    client, service, _, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        for i in range(123):
            observe(session, feed, i)
        session.commit()
    body = {'request_key': str(uuid4()), 'expected_revision': value['revision'], 'product': 'pharma',
        'question': 'How do these changes affect our medicines dossier?'}
    response = post(client, f'/api/feeds/{value["id"]}/dossiers', body)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created['link']['pending_count'] == 123
    assert post(client, f'/api/feeds/{value["id"]}/dossiers', body).json()['dossier_id'] == created['dossier_id']
    with service.db.session() as session:
        run = session.get(Investigation, created['investigation']['id'])
        parent = session.get(ProductDossier, created['dossier_id'])
        assert run.question == body['question'] and run.research_state['admission']['dossier_id'] == parent.id
        feed_research.seed(session, run, parent, service.settings)
        session.flush()
        branches = list(session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run.id)))
        assert len([b for b in branches if b.checkpoint.get('feed_update_id')]) == 123
        assert session.scalar(select(func.count()).select_from(FeedImport).where(FeedImport.status == 'seeded')) == 123
        feed = session.get(Feed, value['id'])
        late, _ = observe(session, feed, 999)
        link = session.get(FeedDossierLink, created['link']['id'])
        assert feed_research.start_pending(session, link) is None  # Never duplicate the active run.
        run.status = 'completed'
        next_run = feed_research.start_pending(session, link)
        assert next_run and next_run.id != run.id and next_run.question == body['question']
        new_imports = list(session.scalars(select(FeedImport).where(FeedImport.investigation_id == next_run.id)))
        assert [row.update_id for row in new_imports] == [late.id]
        session.commit()
    # Standalone feeds do not use dossier slots; explicit creation uses the shared allowance.
    for _ in range(2):
        assert post(client, f'/api/feeds/{value["id"]}/dossiers', {**body, 'request_key': str(uuid4()), 'product': 'legal'}).status_code == 201
    denied = post(client, f'/api/feeds/{value["id"]}/dossiers', {**body, 'request_key': str(uuid4())})
    assert denied.status_code == 429 and denied.json()['code'] == 'dossier_allowance_exhausted'


def test_two_dossiers_use_own_questions_detach_and_revoked_authority_stop_future_work(signed):
    client, service, identity, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        observe(session, session.get(Feed, value['id']), 1)
        session.commit()
    first, _ = create(client)
    second, _ = create(client)
    links = []
    for doc in (first, second):
        path = f'/api/products/pharma/dossiers/{doc["id"]}/feeds'
        command = {'feed_id': value['id'], 'request_key': str(uuid4()), 'expected_feed_revision': value['revision'],
            'question': 'What do source changes mean for dossier ' + doc['id'] + '?'}
        result = post(client, path, command)
        assert result.status_code == 200, result.text
        assert post(client, path, command).json()['id'] == result.json()['id']
        links.append((path, result.json()))
    path, link = links[0]
    detached = client.delete(path + '/' + link['id'], headers=_csrf(client), params={'expected_revision': link['revision']})
    assert detached.status_code == 200 and detached.json()['status'] == 'detached'
    with service.db.session() as session:
        first_run = session.get(Investigation, link['investigation']['id'])
        with pytest.raises(DomainError):
            feed_research.worker_access(session, first_run)
        second_run = session.get(Investigation, links[1][1]['investigation']['id'])
        assert feed_research.worker_access(session, second_run).id == second['id']
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity['user']['id']))
        member.role = 'viewer'
        session.flush()
        with pytest.raises(DomainError):
            feed_research.worker_access(session, second_run)


@pytest.mark.asyncio
async def test_feed_original_reuses_complete_saved_document_without_network(signed):
    from helvetic_lens.product_document_reading import prepare
    from helvetic_lens.product_document_storage import read

    client, service, _, _ = signed
    value, _ = new_feed(client)
    text = 'Earlier source conditions. ' * 1600 + 'THE FINAL EXCEPTION MUST REMAIN AVAILABLE.'
    body = text.encode()
    original = retain(service.environment_settings.storage_path / 'artifacts', 'feed-test', body,
        {'title': 'original.txt', 'content_type': 'text/plain', 'url': 'https://example.org/long',
         'fetched_at': '2026-10-14T08:00:00+00:00'})
    with service.db.session() as session:
        update, _ = observe(session, session.get(Feed, value['id']), 1, url=original['url'], text=text,
            snapshot={'retained_document': original, 'reading_complete': True})
        update_id = update.id
        session.commit()
    result = post(client, f'/api/feeds/{value["id"]}/dossiers', {'request_key': str(uuid4()),
        'expected_revision': value['revision'], 'product': 'legal', 'question': 'Which exceptions matter here?'}).json()
    with service.db.session() as session:
        run = session.get(Investigation, result['investigation']['id'])
        feed_research.seed(session, run, session.get(ProductDossier, run.dossier_id), service.settings)
        session.flush()
        branch = next(b for b in session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run.id))
            if b.checkpoint.get('feed_update_id') == update_id)
        state = branch.checkpoint
        work = {}
        prepare(run, state, work)
        collected = []
        while True:
            result = await read(service, work)
            collected.extend(p['text'] for p in result['excerpts'])
            if not result['reading']['next_cursor']:
                break
            work['document_cursor'] = result['reading']['next_cursor']
        assert ''.join(collected) == text and result['reading']['complete']
    original_response = client.get(f'/api/feeds/{value["id"]}/updates/{update_id}/original')
    assert original_response.status_code == 200 and original_response.content == body
    (service.environment_settings.storage_path / 'artifacts' / original['artifact_key']).write_bytes(b'tampered')
    assert client.get(f'/api/feeds/{value["id"]}/updates/{update_id}/original').status_code == 503


@pytest.mark.parametrize('source', ['http://example.org/source', 'https://user:secret@example.org/private', 'unknown_catalogue'])
def test_source_config_rejects_unapproved_reference_shapes(signed, source):
    client, _, _, _ = signed
    result = post(client, '/api/feeds', {'request_key': str(uuid4()), 'name': 'Feed', 'query': 'A specific research question',
        'product': 'legal', 'sources': [source]})
    assert result.status_code == 422


def test_native_worker_reads_each_retained_version_and_preserves_cited_dossier_answer(signed, monkeypatch):
    import json

    from test_product_exploration import adapters
    from test_product_investigations import tick
    from test_product_iterative_research import GRANT, RECIPIENT

    from helvetic_lens.product_investigation_models import InvestigationSource

    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete

    async def actual_locators(system, user, **kwargs):
        data = json.loads(user)
        response = json.loads(await base(system, user, **kwargs))
        if data.get('document_section'):
            passage = data['source']['excerpts'][0]
            response['section_review'] = {'coverage_fingerprint': data['document_section']['coverage_fingerprint'],
                'summary': 'The complete retained original describes the reported grant.',
                'observations': [{'statement': passage['text'], 'role': 'context',
                    'quote': passage['text'], 'locator': passage['passage']}], 'cross_references': [], 'limitations': []}
        if kwargs['response_schema']['title'] == 'Briefing' and data.get('research_mission'):
            source = data['sources'][0]
            passage = source['excerpts'][0]
            response['mission_checkpoint'] = {'answer': {'status': 'partial', 'points': [
                {'statement': 'The retained public records describe the grant and require contextual comparison.',
                    'evidence': [{'source_id': source['id'], 'quote': passage['text'],
                        'locator': passage['passage'], 'role': 'context'}]}],
                'limitations': ['The fixture does not establish the reason for the amount difference.']},
                'action': 'finish', 'reason': 'Saved originals were read and remaining uncertainty is named.', 'next_checks': []}
        sources = data.get('sources', []) + ([data['source']] if 'source' in data else [])
        passages = {source['id']: {p['text']: p['passage'] for p in source.get('excerpts', [])} for source in sources}
        def locators(item, source_id=None):
            if isinstance(item, dict):
                source_id = item.get('source_id', source_id)
                source_passages = passages.get(source_id, {})
                if item.get('quote') in source_passages and 'locator' in item:
                    item['locator'] = source_passages[item['quote']]
                for value in item.values():
                    locators(value, source_id)
            elif isinstance(item, list):
                for value in item:
                    locators(value, source_id)
        locators(response, data.get('source', {}).get('id'))
        return json.dumps(response)

    monkeypatch.setattr(model, 'complete', actual_locators)
    value, _ = new_feed(client)
    updates = []
    with service.db.session() as session:
        feed = session.get(Feed, value['id'])
        for index, text in enumerate((GRANT, RECIPIENT, GRANT)):
            original = retain(service.environment_settings.storage_path / 'artifacts', f'feed-version-{index}', text.encode(),
                {'title': 'Original.txt', 'content_type': 'text/plain', 'url': 'https://example.org/retained',
                    'fetched_at': '2026-10-14T08:00:00+00:00'})
            row, _ = observe(session, feed, index, url=original['url'], text=text,
                snapshot={'retained_document': original, 'reading_complete': True})
            updates.append(row.id)
        session.commit()
    response = post(client, f'/api/feeds/{value["id"]}/dossiers', {'request_key': str(uuid4()),
        'expected_revision': value['revision'], 'product': 'pharma', 'question': 'Who received the foundation grants?'}).json()
    run_id = response['investigation']['id']
    for _ in range(120):
        tick(service, run_id)
        with service.db.session() as session:
            run = session.get(Investigation, run_id)
            if run.status not in {'queued', 'running'}:
                break
    else:
        pytest.fail('The native retained-source research did not reach a saved result.')
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        sources = list(session.scalars(select(InvestigationSource).where(InvestigationSource.investigation_id == run.id)))
        retained = [source for source in sources if source.snapshot.get('feed_update_id')]
        assert {source.snapshot['feed_update_id'] for source in retained} == set(updates)
        assert len(retained) == 3  # A -> B -> A stays three observations, with citations for each version.
        assert all(source.snapshot.get('analysis_completed') for source in retained), [(s.title, s.snapshot) for s in retained]
        assert 'https://example.org/retained' not in trace['reads']  # Saved original was read locally.
        assert run.status == 'completed', run.stop_reason
        assert run.research_state['exploration']['briefing']['findings']
        original = retain(service.environment_settings.storage_path / 'artifacts', 'feed-later-version', RECIPIENT.encode(),
            {'title': 'Later original.txt', 'content_type': 'text/plain', 'url': 'https://example.org/retained',
                'fetched_at': '2026-10-14T09:00:00+00:00'})
        changed, _ = observe(session, session.get(Feed, value['id']), 99, url=original['url'], text=RECIPIENT,
            snapshot={'retained_document': original, 'reading_complete': True})
        changed_id = changed.id
        session.commit()
    scheduled = feed_research.enqueue_pending(service.db, service.settings)
    assert scheduled['feed_investigations_started'] == 1
    with service.db.session() as session:
        later = session.scalar(select(Investigation).where(Investigation.dossier_id == response['dossier_id'],
            Investigation.id != run_id))
        later_id = later.id
        assert later.research_state['exploration']['previous']['investigation_id'] == run_id
        assert later.question == 'Who received the foundation grants?'
    for _ in range(120):
        tick(service, later_id)
        with service.db.session() as session:
            later = session.get(Investigation, later_id)
            if later.status not in {'queued', 'running'}:
                break
    else:
        pytest.fail('The scheduled source change did not reach a saved dossier result.')
    with service.db.session() as session:
        later = session.get(Investigation, later_id)
        assert later.status == 'completed', later.stop_reason
        assert later.research_state['exploration']['briefing']['findings']
        later_source = next(source for source in session.scalars(select(InvestigationSource).where(
            InvestigationSource.investigation_id == later_id)) if source.snapshot.get('feed_update_id') == changed_id)
        assert later_source.snapshot['analysis_completed']
        assert later_source.sha256 == hashlib.sha256(RECIPIENT.encode()).hexdigest()
        previous = session.get(Investigation, run_id)
        assert previous.status == 'completed' and previous.research_state['exploration']['briefing']['findings']
    assert any(item['phase'] == 'ResearchPlan' and item['input'].get('previous_public_briefing') for item in trace['models'])
    assert 'https://example.org/retained' not in trace['reads']


def test_link_requires_explicit_public_question_and_private_work_cannot_replace_it(signed):
    client, service, identity, _ = signed
    value, _ = new_feed(client)
    document, _ = create(client)
    path = f'/api/products/pharma/dossiers/{document["id"]}/feeds'
    command = {'feed_id': value['id'], 'request_key': str(uuid4()), 'expected_feed_revision': value['revision']}
    assert post(client, path, command).json()['code'] == 'feed_question_required'
    public_question = 'How does this public framework affect the approved project?'
    result = post(client, path, {**command, 'question': public_question})
    assert result.status_code == 200, result.text
    with service.db.session() as session:
        session.add(Investigation(dossier_id=document['id'], request_key=str(uuid4()),
            question='PRIVATE_CLIENT_SETTLEMENT_DO_NOT_SEARCH', external_discovery=False,
            actor_user_id=identity['user']['id'], created_by_user_id=identity['user']['id'], status='completed'))
        observe(session, session.get(Feed, value['id']), 1)
        session.flush()
        link = session.get(FeedDossierLink, result.json()['id'])
        run = feed_research.start_pending(session, link)
        assert run.question == public_question
        assert run.research_state['feed_origin']['previous_investigation_id'] is None
        assert 'PRIVATE_CLIENT_SETTLEMENT' not in str(run.research_state)


def test_failed_feed_history_waits_for_explicit_retry_and_detach_recovery(signed):
    client, service, _, _ = signed
    value, _ = new_feed(client)
    with service.db.session() as session:
        observe(session, session.get(Feed, value['id']), 1)
        session.commit()
    result = post(client, f'/api/feeds/{value["id"]}/dossiers', {'request_key': str(uuid4()),
        'expected_revision': value['revision'], 'product': 'legal', 'question': 'Which changes affect this question?'}).json()
    link_id, run_id = result['link']['id'], result['investigation']['id']
    path = f'/api/products/legal/dossiers/{result["dossier_id"]}/feeds'
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        feed_research.seed(session, run, session.get(ProductDossier, run.dossier_id), service.settings)
        session.flush()
        run.status = 'failed'
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run.id,
            InvestigationBranch.phase == 'plan'))
        branch.status = 'failed'
        observe(session, session.get(Feed, value['id']), 2)
        assert feed_research.start_pending(session, session.get(FeedDossierLink, link_id)) is None
        run_revision = run.revision
        session.commit()
    retry = {'request_key': str(uuid4()), 'expected_revision': result['link']['revision'],
        'investigation_id': run_id, 'expected_investigation_revision': run_revision}
    assert post(client, path + '/' + link_id + '/retry', {**retry, 'expected_investigation_revision': run_revision + 1}).status_code == 409
    resumed = post(client, path + '/' + link_id + '/retry', retry)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['investigation']['id'] == run_id
    assert post(client, path + '/' + link_id + '/retry', retry).status_code == 200
    with service.db.session() as session:
        assert session.get(Investigation, run_id).status == 'queued'
        assert session.scalar(select(func.count()).select_from(FeedImport)) == 2
    detached = client.delete(path + '/' + link_id, headers=_csrf(client), params={'expected_revision': 1})
    assert detached.status_code == 200
    assert post(client, path + '/' + link_id + '/retry', {**retry, 'request_key': str(uuid4()), 'expected_revision': 2}).status_code == 403
    again = post(client, path, {'request_key': str(uuid4()), 'feed_id': value['id'],
        'expected_feed_revision': value['revision'], 'question': 'Which changes affect this question?'})
    assert again.status_code == 200, again.text
    new_run_id = again.json()['investigation']['id']
    assert new_run_id != run_id
    with service.db.session() as session:
        assert session.get(Investigation, run_id).status == 'cancelled'
        assert session.scalar(select(func.count()).select_from(FeedImport).where(FeedImport.investigation_id == new_run_id)) == 2


def test_pausing_active_collection_closes_check_and_keeps_safe_failure_receipts(signed):
    from helvetic_lens.feed_models import FeedCheck
    from helvetic_lens.models import Job

    client, service, _, _ = signed
    value, body = new_feed(client, status='active')
    with service.db.session() as session:
        check = session.scalar(select(FeedCheck).where(FeedCheck.feed_id == value['id']))
        check.receipts_json = {**check.receipts_json, 'captured': 2, 'failures': [
            {'phase': 'read', 'url': 'https://example.org/unavailable', 'code': 'source_unavailable',
                'retained_document': {'artifact_key': 'SECRET-KEY'}}]}
        session.commit()
    command = {key: body[key] for key in ('name', 'query', 'sources', 'status')}
    command.update(status='paused', request_key=str(uuid4()), expected_revision=value['revision'])
    changed = client.patch('/api/feeds/' + value['id'], headers=_csrf(client), json=command)
    assert changed.status_code == 200
    checks = client.get('/api/feeds/' + value['id'] + '/checks').json()['items']
    assert checks[0]['status'] == 'cancelled' and checks[0]['finished_at']
    assert checks[0]['progress']['captured'] == 2 and checks[0]['progress']['failures'][0]['code'] == 'source_unavailable'
    assert 'SECRET-KEY' not in str(checks)
    with service.db.session() as session:
        assert session.get(Job, value['job']['id']).state == 'cancelled'
