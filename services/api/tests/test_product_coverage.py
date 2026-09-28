"""Read actual retained coverage without authorizing collection or exposing peers."""
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import LAW_URL
from sqlalchemy import func, select
from test_auth import _register
from test_private_dossier_monitoring import private, remove
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_source_health import connected
from test_product_teams import switch

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import Job, MonitoringTopicRevision, SourcePackDefinition, SourcePackSubscription
from helvetic_lens.product_investigation_models import Investigation, WebResearchPolicy, WebResearchTrigger
from helvetic_lens.product_models import DossierEntry


def test_draft_read_has_planned_sources_and_creates_no_work(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    def counts():
        with service.db.session() as session:
            return [session.scalar(select(func.count()).select_from(table)) for table in
                    (Job, DossierEntry, SourcePackSubscription, Investigation, WebResearchPolicy)]
    before = counts()
    result = client.get(ROOT + '/' + doc['id'] + '/coverage')
    assert result.status_code == 200 and 'no-store' in result.headers['cache-control']
    body = result.json()
    assert body['schema_id'] == 'dossier-coverage/v1' and body['scope'] == 'saved_operational_state'
    assert body['profile_status'] == 'draft' and body['topics'] == [] and body['documents'] == []
    assert [pack['id'] for pack in body['packs']] == doc['profile']['config']['source_pack_ids']
    assert not body['web_research']['enabled'] and body['web_research']['latest_run'] is None
    assert body['ai_calls'] == 0 and len(body['limitations']) == 4
    assert counts() == before and model.calls == []


def test_current_revisions_retain_inactive_missing_unsupported_and_missing_topics(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    topic = active(client, doc)['topics'][0]
    with service.db.session() as session:
        revision = session.scalar(select(MonitoringTopicRevision).where(MonitoringTopicRevision.topic_id == topic['id']))
        revision.source_pack_ids_json = ['fedlex-legislation', 'retired-source']
        pack = session.get(SourcePackDefinition, 'fedlex-legislation')
        pack.active = False
        pack.filters_json = {'streams': [['unverified', 'custom-feed']]}
        profile = session.get(LegalMonitoringProfile, doc['profile']['id'])
        profile.topic_ids_json = [*profile.topic_ids_json, str(uuid4())]
        session.commit()
    result = client.get(ROOT + '/' + doc['id'] + '/coverage').json()
    packs = {p['id']: p for p in result['packs']}
    assert packs['fedlex-legislation']['definition_state'] == 'inactive'
    assert packs['fedlex-legislation']['unsupported_streams'] == [{'connector': 'unverified', 'stream': 'custom-feed'}]
    assert packs['retired-source']['definition_state'] == 'missing' and packs['retired-source']['streams'] == []
    assert result['topics'][0]['pack_ids'] == ['fedlex-legislation', 'retired-source']
    assert result['topics'][-1]['status'] == 'missing' and result['topics'][-1]['revision'] is None
    assert model.calls == []


def test_failed_page_preserves_success_in_coverage_and_deduplicates(signed):
    client, service, _, _ = signed
    root, law_id = connected(client)
    before = client.get(root + '/coverage').json()['documents'][0]
    service.fetcher.values[LAW_URL] = DomainError('Source unavailable', 502, 'source_unavailable')
    assert post(client, '/api/scans', {'law_ids': [law_id]}).json()['status'] == 'partial'
    data = client.get(root + '/coverage').json()
    assert len(data['documents']) == 1
    page = data['documents'][0]
    assert page['last_result'] == 'failed' and page['last_error']
    assert page['last_success_at'] == before['last_success_at'] < page['last_checked']


@pytest.mark.parametrize('product', ['pharma', 'legal'])
def test_guest_viewer_reads_only_granted_dossier_and_revocation_removes_coverage(signed, product):
    client, service, _, model = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    doc, root, _ = private(client, product)
    _, sibling, _ = private(client, product)
    invite = invitation(client, root, account, 'VIEWER')
    switch(client, cookies)
    assert client.get(root + '/coverage').status_code == 404
    accept(client, root, invite)
    result = client.get(root + '/coverage')
    assert result.status_code == 200, result.text
    assert result.json()['dossier_id'] == doc['id'] and result.json()['topics']
    assert result.json()['packs'][0]['subscription_enabled']
    assert client.get(sibling + '/coverage').status_code == 404
    assert client.get('/api/monitoring-profiles/' + doc['profile']['id']).status_code == 404
    assert client.get(root.replace(product, 'legal' if product == 'pharma' else 'pharma') + '/coverage').status_code == 404
    switch(client, owner)
    remove(client, root, account['user']['id'])
    switch(client, cookies)
    assert client.get(root + '/coverage').status_code == 404
    client.cookies.clear()
    assert client.get(root + '/coverage').status_code == 401
    assert model.calls == []


def test_foreign_workspace_has_no_coverage_or_private_error(signed):
    client, _, _, _ = signed
    root, _ = connected(client)
    assert _register(client, 'foreign-coverage@example.ch').status_code == 201
    response = client.get(root + '/coverage')
    assert response.status_code == 404 and 'documents' not in response.text


def test_scheduler_check_and_failed_older_search_are_not_source_success(signed):
    client, service, identity, model = signed
    doc, _ = create(client)
    now = utcnow()
    with service.db.session() as session:
        scope = {'dossier_id': doc['id'], 'organization_id': identity['organization']['id']}
        policy = WebResearchPolicy(**scope, enabled=False, revision=2, checked_at=now,
            reason='Settings paused. Previous research retained.')
        run = Investigation(**scope, request_key=str(uuid4()), question='Public test question', status='failed')
        session.add_all([policy, run])
        session.flush()
        session.add(WebResearchTrigger(**scope, policy_id=policy.id, policy_revision=1, investigation_id=run.id,
            question=run.question, scheduled_for=now - timedelta(days=1)))
        session.commit()
    result = client.get(ROOT + '/' + doc['id'] + '/coverage').json()['web_research']
    assert not result['enabled'] and result['next_run_at'] is None
    assert result['last_scheduler_check_at'] == now.isoformat()
    assert result['latest_run']['status'] == 'failed' and result['latest_run']['policy_revision'] < result['revision']
    assert 'last_success_at' not in result and model.calls == []
