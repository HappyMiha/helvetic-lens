"""Product work must be durable, assigned safely and backed by current evidence."""
from datetime import timedelta
from uuid import uuid4

from test_account_deletion_migration import config as migration_config
from test_auth import _csrf, _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_research import contribution, question
from test_topic_matching import add_event

from alembic import command
from helvetic_lens import topic_matching
from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
from helvetic_lens.models import OrganizationMembership, RegulatoryEvent, User
from helvetic_lens.product_models import DossierAction, DossierEntry, ProductDossier, ResearchThread
from helvetic_lens.product_operations import today


def put(client, path, data):
    return client.put(path, headers=_csrf(client), json=data)


def action(client, route, **fields):
    values = {'creation_key':str(uuid4()),'title':'Review the source and record implications',**fields}
    result = post(client, route+'/actions', values)
    assert result.status_code == 201, result.text
    return result.json(), values


def test_context_reviews_revisions_actions_outcomes_and_printable_brief(signed):
    client, _, identity, _ = signed
    doc, _ = create(client)
    active(client, doc)
    route = ROOT+'/'+doc['id']
    values = {'expected_revision':1, 'context':{'subject':'Medicine <script>alert(1)</script>','reference':'Review 42','jurisdictions':'CH','category':'Marketed'},'priority':'high','owner_user_id':identity['user']['id'],'next_review_on':today().isoformat()}
    work = put(client, route+'/work', values)
    assert work.status_code == 200, work.text
    assert work.json()['owner']['name'] == 'Ada Example' and work.json()['revision'] == 2
    assert put(client, route+'/work', values).status_code == 409
    queue = client.get('/api/products/pharma/workbench').json()
    assert queue['counts']['reviews_due'] == 1 and queue['reviews'][0]['id'] == doc['id']
    saved, original = action(client, route, due_on=(today()-timedelta(days=1)).isoformat(), assignee_user_id=identity['user']['id'], source_url='https://www.fedlex.admin.ch/')
    assert saved['overdue'] and saved['assignee']['id'] == identity['user']['id']
    assert post(client, route+'/actions', original).json()['id'] == saved['id']
    assert post(client, route+'/actions', {**original, 'title':'Changed title'}).status_code == 409
    update = {'expected_revision':1,'title':saved['title'],'status':'done','assignee_user_id':identity['user']['id'],'outcome':''}
    assert put(client, route+'/actions/'+saved['id'],update).status_code == 422
    assert put(client, route+'/actions/'+saved['id'],{**update,'outcome':'Reviewed. Update the programme plan.'}).status_code == 200
    assert put(client, route+'/actions/'+saved['id'],{**update,'outcome':'Attempt to overwrite'}).status_code == 409
    review = {'expected_revision':2,'request_key':str(uuid4()),'note':'Discussed the source. Follow the next revision.','next_review_on':(today()+timedelta(days=7)).isoformat()}
    assert post(client, route+'/review',review).status_code == 200
    assert post(client, route+'/review',review).status_code == 200
    assert post(client, route+'/review',{**review,'note':'Changed decision'}).status_code == 409
    queue = client.get('/api/products/pharma/workbench').json()
    assert queue['counts'] == {'open':0,'overdue':0,'unassigned':0,'completed_week':1,'reviews_due':0}
    brief = client.get(route+'/brief')
    assert brief.status_code == 200 and '<script>alert(1)</script>' not in brief.text
    assert '&lt;script&gt;' in brief.text and 'Reviewed. Update the programme plan.' in brief.text
    assert "default-src 'none'" in brief.headers['content-security-policy'] and 'no-store' in brief.headers['cache-control']
    exported = client.get(route+'/export').json()
    assert exported['actions'][0]['outcome'] == 'Reviewed. Update the programme plan.'
    assert len([e for e in exported['entries'] if e['title']=='Review recorded']) == 1
    assert 'Ada Example' not in str([e['data'] for e in exported['entries']])


def test_queue_totals_pagination_assignment_and_product_scope(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    active(client, doc)
    route = ROOT+'/'+doc['id']
    with service.db.session() as session:
        for index in range(55):
            session.add(DossierAction(dossier_id=doc['id'],creation_key=str(uuid4()),creation_fingerprint='a'*64,
                title=f'Assess evidence {index}', due_on=today()-timedelta(days=1),
                assignee_user_id=identity['user']['id'] if index==0 else None))
        session.commit()
    result = client.get('/api/products/pharma/workbench').json()
    assert result['total']==55 and len(result['items'])==50
    assert result['counts']['open']==55 and result['counts']['overdue']==55 and result['counts']['unassigned']==54
    page = client.get('/api/products/pharma/workbench?offset=50').json()
    assert len(page['items'])==5 and not {x['id'] for x in page['items']} & {x['id'] for x in result['items']}
    assert client.get('/api/products/pharma/workbench?scope=mine').json()['total']==1
    filtered = client.get('/api/products/pharma/workbench?q=evidence%2054').json()
    assert filtered['total']==1 and filtered['counts']['open']==55
    assert client.get('/api/products/loyer/workbench').json()['total']==0
    assert post(client,route+'/actions',{'creation_key':str(uuid4()),'title':'Unsafe source','source_url':'javascript:alert(1)'}).status_code==422
    assert post(client,route+'/actions',{'creation_key':str(uuid4()),'title':'Foreign owner','assignee_user_id':str(uuid4())}).status_code==422
    assert put(client,route+'/work',{'expected_revision':1,'context':{},'owner_user_id':str(uuid4())}).status_code==422
    assert _register(client,'other@example.ch').status_code==201
    assert client.get('/api/products/pharma/workbench').json()['total']==0
    assert client.get(route+'/actions').status_code==404 and client.get(route+'/brief').status_code==404


def test_readonly_members_see_shared_work_and_cannot_change_it(signed):
    client,service,identity,_=signed
    private,_=create(client)
    shared,_=create(client)
    active(client,shared)
    for doc in (private,shared):
        action(client,ROOT+'/'+doc['id'])
    reader=_register(client,'reader@example.ch').json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader['user']['id'],organization_id=identity['organization']['id'],role='viewer'))
        session.commit()
    post(client,'/api/auth/session/organization',{'organization_id':identity['organization']['id']})
    result=client.get('/api/products/pharma/workbench').json()
    assert result['total']==1 and result['items'][0]['dossier_id']==shared['id']
    path=ROOT+'/'+shared['id']
    assert post(client,path+'/actions',{'creation_key':str(uuid4()),'title':'Not permitted'}).status_code==403
    assert put(client,path+'/work',{'expected_revision':1,'context':{}}).status_code==403
    assert post(client,path+'/review',{'expected_revision':1,'request_key':str(uuid4()),'note':'Not permitted'}).status_code==403
    assert client.get(ROOT+'/'+private['id']+'/brief').status_code==404


def test_action_links_only_current_matching_evidence(signed):
    client,service,_,_=signed
    doc,_=create(client)
    profile=active(client,doc)
    event_id=add_event(service)
    with service.db.session() as session:
        event=session.get(RegulatoryEvent,event_id)
        topic_matching.generate_for_events(session,[event],service.settings)
        session.commit()
    matches=client.get('/api/monitoring-topics/'+profile['topic_ids'][0]+'/matches').json()
    assert matches and matches[0]['is_current']
    match=matches[0]
    route=ROOT+'/'+doc['id']
    saved,_=action(client,route,match_id=match['id'],evaluation_fingerprint=match['evaluation_fingerprint'])
    assert saved['source_url']==match['evidence']['source_url'] and saved['evidence']['event_id']==event_id
    assert post(client,route+'/actions',{'creation_key':str(uuid4()),'title':'Stale match','match_id':match['id'],'evaluation_fingerprint':'stale'}).status_code==409
    foreign,_=create(client)
    assert post(client,ROOT+'/'+foreign['id']+'/actions',{'creation_key':str(uuid4()),'title':'Foreign evidence','match_id':match['id'],'evaluation_fingerprint':match['evaluation_fingerprint']}).status_code==404


def test_migration_preserves_existing_dossier_notes_and_files(signed):
    client,service,_,_=signed
    doc,_=create(client)
    route=ROOT+'/'+doc['id']
    note=post(client,route+'/entries',{'request_key':str(uuid4()),'kind':'note','body':'Preserve this existing note.'}).json()
    file=client.post(route+'/files',headers=_csrf(client),files={'file':('report.txt',b'Preserve these evidence bytes')}).json()
    with service.db.engine.connect() as connection:
        command.downgrade(migration_config(connection),'f3c495bef124')
        assert connection.exec_driver_sql('SELECT count(*) FROM product_dossier_entries').scalar()==2
        command.upgrade(migration_config(connection),'head')
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all()==[]
    saved=client.get(route).json()
    assert saved['work']['revision']==1 and saved['work']['priority']=='normal'
    assert {e['id'] for e in saved['entries']}=={note['id'],file['id']}
    assert client.get(route+'/files/'+file['id']).content==b'Preserve these evidence bytes'


def test_account_erasure_detaches_author_and_owner_but_retains_team_answers(signed):
    client,service,identity,_=signed
    doc,_=create(client)
    active(client,doc)
    route=ROOT+'/'+doc['id']
    saved,_=action(client,route,assignee_user_id=identity['user']['id'])
    thread,_=question(client,route)
    reply,_=contribution(client,route+'/discussion/'+thread['id'])
    post(client,route+'/discussion/'+thread['id']+'/accept',{'expected_revision':2,'entry_id':reply['id']})
    put(client,route+'/work',{'expected_revision':1,'context':{},'owner_user_id':identity['user']['id']})
    with service.db.session(include_all_organizations=True) as session:
        user=session.get(User,identity['user']['id'])
        selection=select_private_rows(session,user,[])
        erase_selected(session,user,selection)
        session.commit()
    with service.db.session() as session:
        retained=session.get(ResearchThread,thread['id'])
        assert retained.created_by_user_id is None and retained.accepted_entry_id==reply['id']
        assert session.get(DossierEntry,reply['id']).actor_user_id is None
        task=session.get(DossierAction,saved['id'])
        assert task.assignee_user_id is None and task.created_by_user_id is None
        assert session.get(ProductDossier,doc['id']).owner_user_id is None
        assert session.connection().exec_driver_sql('PRAGMA foreign_key_check').all()==[]
