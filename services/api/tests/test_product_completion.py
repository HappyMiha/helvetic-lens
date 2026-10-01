"""Integrated continuation, scheduled mission and personal delivery behavior."""
import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from test_product_decision_search import transport
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_iterative_research import complete
from test_product_research_following import finished
from test_product_web_research import due, enable, newest, setup

from helvetic_lens import decision_search
from helvetic_lens import product_dossier_delivery as mail
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, User
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_models import PrivateDossierFollow


def finish_mission(monkeypatch, model, *, deepen=False):
    base = model.complete
    async def answer(system, user, **kwargs):
        if kwargs['response_schema']['title'] == 'Comparison':
            return json.dumps({'changes': []})
        value = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'Briefing':
            data = json.loads(user)
            source = data['sources'][0]
            passage = source['excerpts'][0]
            frontier = data['research_mission']['discovery_frontiers']
            more = deepen and data['research_mission']['round'] == 1 and frontier
            value.update(clarification='', directions=[], mission_checkpoint={
                'answer': {'status': 'partial', 'points': [{'statement': passage['text'], 'evidence': [{
                    'source_id': source['id'], 'locator': passage['passage'], 'quote': passage['text'], 'role': 'support'}]}],
                    'limitations': ['The fixture does not settle the discrepancy.']},
                'action': 'continue' if more else 'finish', 'reason': 'Check the available later catalogue page.' if more else 'Useful available checks are complete.',
                'deepen_branches': [frontier[0]['branch_id']] if more else []})
        return json.dumps(value)
    monkeypatch.setattr(model, 'complete', answer)


def test_scheduled_checks_use_completion_mission_without_daily_start_quota(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    from pydantic import SecretStr
    service.settings.typesafe_api_key = SecretStr('fixture')
    service.settings.apertus_base_url = 'https://fixture.invalid/v1'
    finish_mission(monkeypatch, model)
    _, root = setup(client)
    enable(client, root)
    for index in range(3):
        assert due(service)['started'] == 1
        current = newest(client, root)
        assert due(service)['started'] == 0  # One active run, no catch-up burst.
        result = complete(client, service, root + '/investigations', current)
        assert result['status'] == 'completed', {'result': result, 'trace': trace}
        assert result['exploration']['mission']['answer']['points']
        assert result['research']['execution_policy'] == 'completion_based'
        assert result['web_research_trigger']
        if index:
            outcome = client.get(root + '/web-research').json()['items'][0]['outcome']
            assert outcome['materiality']['category'] == 'quiet', outcome
    policy = client.get(root + '/web-research').json()['policy']
    assert policy['daily_limit'] is None and policy['used_today'] == 3
    assert len(trace['reads']) >= 3  # Retained sources are refreshed on each check.
    enable(client, root, enabled=False)
    assert due(service)['started'] == 0


def test_native_mission_resumes_a_saved_page_without_replaying_prior_candidates(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = decision_search.federated_retrieve
    requests = []
    async def paged(settings, query, *args, **kwargs):
        requests.append((query, kwargs.get('cursors')))
        value = await base(settings, query, *args)
        if kwargs.get('cursors'):
            value['items'] = []  # Exhaustion is persisted; no duplicate reading.
        else:
            value['next_cursors'] = {'broad': '2'}
        return value
    monkeypatch.setattr(decision_search, 'federated_retrieve', paged)
    finish_mission(monkeypatch, model, deepen=True)
    root, run, _ = start(client)
    result = complete(client, service, root + '/investigations', run)
    assert result['status'] == 'completed'
    assert any(cursor == {'broad': '2'} for _, cursor in requests)
    assert len(trace['reads']) == len(set(trace['reads']))
    with service.db.session() as session:
        continued = [b for b in session.scalars(select(InvestigationBranch)) if len(b.checkpoint.get('discovery_history', [])) > 1]
        assert continued and not continued[0].checkpoint['next_discovery_cursors']
    assert len(result['exploration']['mission']['checkpoints']) == 2


def test_provider_page_is_fixed_host_and_failed_lane_does_not_erase_cursor(monkeypatch):
    calls = []
    def response(request):
        calls.append(request)
        if request.url.host == 'search.local':
            assert request.url.params['pageno'] == '2'
            return httpx.Response(503)
        assert request.url.host == 'api.crossref.org'
        assert request.url.params['cursor'] == 'opaque-page-2'
        return httpx.Response(200, json={'message': {'items': [{'title': ['Original record'], 'URL': 'https://doi.org/10.123/record'}], 'next-cursor': 'opaque-page-3'}})
    transport(monkeypatch, response)
    settings = Settings(web_search_provider='searxng', searxng_base_url='http://search.local')
    value = asyncio.run(decision_search.federated_retrieve(settings, 'question', 'web', 'balanced', 'legal',
        cursors={'broad': '2', 'crossref': 'opaque-page-2'}, complete_page=True))
    assert len(calls) == value['search_requests'] == 2
    assert value['next_cursors'] == {'crossref': 'opaque-page-3'}
    assert len(value['items']) == 1 and value['status'] == 'partial'


class Mailbox:
    def __init__(self, fail=False):
        self.messages, self.fail = [], fail

    def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))
        if self.fail:
            raise RuntimeError('SMTP response uncertain')
        return 'smtp'


def email_setup(signed):
    client, service, identity, _ = signed
    doc, root = setup(client)
    body = {'following': True, 'expected_revision': 0, 'email_mode': 'daily'}
    assert post(client, root + '/follow', body).status_code == 422
    with service.db.session() as session:
        session.get(User, identity['user']['id']).email_verified_at = utcnow()
        session.commit()
    body['email_confirmed'] = True
    response = post(client, root + '/follow', body)
    assert response.status_code == 200, response.text
    finished(service, doc)
    settings = service.settings.model_copy(update={'auth_email_mode': 'smtp'})
    assert mail.enqueue_due(service.db, settings)['queued'] == 0  # Daily, not immediate.
    assert mail.enqueue_due(service.db, settings, now=utcnow() + timedelta(days=1, seconds=1))['queued'] == 1
    with service.db.session() as session:
        job = session.scalar(select(Job).where(Job.type == mail.MAIL_JOB))
        return doc, root, settings, job.target_id, dict(job.payload)


def test_email_opt_in_exact_once_replay_and_dossier_scoped_message(signed):
    _, _, settings, target, payload = email_setup(signed)
    _, service, _, _ = signed
    mailbox = Mailbox()
    assert mail.deliver(service.db, settings, target, payload, mailer=mailbox)['state'] == 'sent'
    assert mail.deliver(service.db, settings, target, payload, mailer=mailbox)['state'] == 'cancelled_or_already_handled'
    assert len(mailbox.messages) == 1
    assert 'https://pharma.helveticlens.ch/?dossier=' in mailbox.messages[0][0][2]
    assert '@helveticlens.ch>' in mailbox.messages[0][1]['message_id']


@pytest.mark.parametrize('withdraw', ['off', 'account', 'source'])
def test_queued_email_rechecks_opt_out_access_and_current_sources(signed, withdraw):
    from uuid import uuid4

    from helvetic_lens.product_models import DossierEntry
    doc, root, settings, target, payload = email_setup(signed)
    client, service, identity, _ = signed
    if withdraw == 'off':
        state = client.get(root + '/follow').json()
        assert post(client, root + '/follow', {'expected_revision': state['revision'], 'following': True, 'email_mode': 'off'}).status_code == 200
    else:
        with service.db.session() as session:
            if withdraw == 'account':
                session.get(User, identity['user']['id']).active = False
            else:
                session.add(DossierEntry(dossier_id=doc['id'], kind='source_review', url='https://example.org/source', request_key=str(uuid4()),
                    data_json={'revision': 1, 'decision': 'exclude'}))
            session.commit()
    mailbox = Mailbox()
    assert mail.deliver(service.db, settings, target, payload, mailer=mailbox)['state'] != 'sent'
    assert mailbox.messages == []


def test_uncertain_email_is_not_automatically_resent(signed):
    _, _, settings, target, payload = email_setup(signed)
    _, service, _, _ = signed
    mailbox = Mailbox(fail=True)
    assert mail.deliver(service.db, settings, target, payload, mailer=mailbox)['state'] == 'delivery_uncertain'
    assert mail.deliver(service.db, settings, target, payload, mailer=mailbox)['state'] == 'delivery_uncertain'
    assert len(mailbox.messages) == 1
    with service.db.session() as session:
        assert session.get(PrivateDossierFollow, target).email_settings['pending']


def test_optional_assessment_never_erases_cited_claims_or_bypasses_current_access(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from helvetic_lens import product_read_relevance as relevance
    from helvetic_lens.config import DomainError
    from helvetic_lens.product_document_analysis import schema
    from helvetic_lens.research_gateway import extraction_citation_errors, response_object

    source = SimpleNamespace(id=str(uuid4()), sha256='a' * 64, snapshot={'excerpts': [
        {'passage': 'p1', 'text': 'The original record states that the measurement is relative to sea level.'}]})
    question_id = str(uuid4())
    typed = schema(relevance.ReadExtraction)
    content = {'claims': [{'statement': 'The stated measurement is relative to sea level.',
        'quote': 'the measurement is relative to sea level.', 'locator': 'p1', 'relation': 'SUPPORTS'}],
        'section_review': {'coverage_fingerprint': 'b' * 64, 'summary': 'The record defines its measurement.'},
        'read_relevance': {'source_id': source.id, 'question_id': question_id, 'category': 'direct',
            'reason': 'The record defines its measurement.', 'quote': 'A fabricated optional quotation.', 'locator': 'missing'}}
    result = typed.model_validate_json(response_object(json.dumps({'ResearchExtraction': content}), typed))
    work = {'unmetered_research': True, 'read_relevance': True, 'read_dependencies': [],
        'input': {'read_question': {'question_id': question_id, 'question': 'Which reference is used?'},
            'source': {'id': source.id, **source.snapshot}}}
    monkeypatch.setattr(relevance, 'current', lambda *args: True)
    assert relevance.validate(None, None, source, work, result) is None
    assert result._optional_omissions == ['read_relevance'] and len(result.claims) == 1
    assert extraction_citation_errors(result, work) == []
    result.claims[0].statement = 'The original specifies 2111 kilometers.'
    assert extraction_citation_errors(result, work)[0]['path'] == ['claims', 0, 'statement']
    result.claims[0].quote = 'An unsupported required claim quotation.'
    assert extraction_citation_errors(result, work)[0]['path'] == ['claims', 0, 'quote']
    monkeypatch.setattr(relevance, 'current', lambda *args: False)
    with pytest.raises(DomainError, match='inputs changed'):
        relevance.validate(None, None, source, work, result)
    malformed = '{"ResearchExtraction":' + json.dumps(content)
    assert response_object(malformed, typed) == malformed  # No fabricated closing tokens.


def test_scheduled_long_original_compares_corresponding_sections(signed):
    from uuid import uuid4

    from helvetic_lens.product_investigation_models import Investigation
    from helvetic_lens.product_investigations import snapshot
    from helvetic_lens.product_web_research import capture

    client, service, _, _ = signed
    doc, _ = setup(client)
    with service.db.session() as session:
        previous = Investigation(dossier_id=doc['id'], organization_id=service.organization_id,
            question='Check this original', request_key=str(uuid4()), status='completed')
        current = Investigation(dossier_id=doc['id'], organization_id=service.organization_id,
            question=previous.question, request_key=str(uuid4()), status='running')
        session.add_all([previous, current])
        session.flush()
        parts = [{'url': 'https://example.org/original.pdf', 'sha256': 'c' * 64,
            'excerpts': [{'passage': f'page-{page}-char-1', 'text': f'Original text on page {page}.'}],
            'reading': {'cursor': {'page': page, 'offset': 0}}, 'analysis_completed': True}
            for page in (0, 400)]
        originals = [snapshot(session, previous, part, public=True)[0] for part in parts]
        for part, original in zip(parts, originals, strict=True):
            observed, fresh = capture(session, current, part, refresh_analysis=True)
            assert fresh and observed.snapshot['allow_discovery']
            assert observed.snapshot['unchanged_from'] == original.id
        changed = Investigation(dossier_id=doc['id'], organization_id=service.organization_id,
            question=previous.question, request_key=str(uuid4()), status='running')
        session.add(changed)
        session.flush()
        observed, _ = capture(session, changed, {**parts[0], 'sha256': 'd' * 64}, refresh_analysis=True)
        assert observed.snapshot['capture_state'] == 'changed' and not observed.snapshot['unchanged_from']


def test_rejected_proposals_keep_grounded_siblings_and_name_partial_answer(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    finish_mission(monkeypatch, model)
    base = model.complete

    async def with_bad_sibling(system, user, **kwargs):
        value = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'ResearchExtraction':
            value['claims'].append({'statement': 'This invented sibling must never enter the dossier.',
                'relation': 'SUPPORTS', 'quote': 'This quotation does not occur in the source.', 'locator': 'p1'})
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', with_bad_sibling)
    root, run, _ = start(client)
    result = complete(client, service, root + '/investigations', run)
    assert result['status'] == 'completed'
    assert result['claims'] and not any('invented sibling' in c['statement'] for c in result['claims'])
    answer = result['exploration']['mission']['answer']
    assert answer['status'] == 'partial' and answer['points']
    assert any('proposed findings could not be verified' in gap for gap in answer['limitations'])


def test_invalid_support_observations_are_gaps_not_arithmetic_evidence():
    from helvetic_lens.product_document_analysis import schema
    from helvetic_lens.product_iterative_research import ResearchExtraction
    from helvetic_lens.research_gateway import retain_grounded_items

    text = 'The two distances are 6384.4 km and 6382.3 km.'
    result = schema(ResearchExtraction).model_validate({'section_review': {
        'coverage_fingerprint': 'b' * 64, 'summary': 'Two quoted geocentric distances.',
        'observations': [{'statement': 'The difference is 2111 km.', 'role': 'support', 'quote': text, 'locator': 'p1'},
            {'statement': 'The source reports two distances.', 'role': 'context', 'quote': text, 'locator': 'p1'}]}})
    retain_grounded_items(result, {'input': {'source': {'excerpts': [{'passage': 'p1', 'text': text}]}}})
    assert len(result.section_review.observations) == 1
    assert result._analysis_gaps == {'section_review.observations': 1}
    assert result.section_review.limitations


def test_native_email_job_uses_the_same_delivery_fences(signed, monkeypatch):
    from test_account_deletion_migration import config as migration_config

    from alembic import command as migrate

    _, _, _, target, _ = email_setup(signed)
    _, service, _, _ = signed
    mailbox = Mailbox()
    monkeypatch.setattr(mail, 'AuthMailer', lambda settings: mailbox)
    with service.db.session() as session:
        job_id = session.scalar(select(Job.id).where(Job.type == mail.MAIL_JOB, Job.target_id == target))
    asyncio.run(service.execute_job(job_id, 'fixture-dossier-email-worker'))
    with service.db.session() as session:
        job = session.get(Job, job_id)
        assert job.state == 'succeeded' and job.result_json['state'] == 'sent'
    assert len(mailbox.messages) == 1
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match='email consent'):
        migrate.downgrade(migration_config(connection), '0dd495bef125')
