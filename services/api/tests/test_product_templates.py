"""Template choices retain guidance and provenance without changing research authority."""
from dataclasses import replace
from types import MappingProxyType
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_account_deletion_migration import config as migration_config
from test_auth import _csrf, _register
from test_legal_profiles import config
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_operations import put
from test_product_publications import PUBLIC, preview_and_publish
from test_product_reuse import prepare
from test_product_teams import managed, switch

from alembic import command
from helvetic_lens import dossier_templates
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profiles import ProfileConfig
from helvetic_lens.models import UserSession
from helvetic_lens.product_models import DossierEntry, DossierMember, ProductDossier


def choose(client, root, template, **changes):
    current = client.get(root).json()
    body = {'expected_revision': current['work']['revision'], 'request_key': str(uuid4()),
            'template': template, **changes}
    return put(client, root + '/template', body), body


@pytest.mark.parametrize('product,first,second', [('pharma', 'market-access', 'safety'),
    ('legal', 'legal-question', 'case-dispute'), ('loyer', 'legal-question', 'legislative-monitor')])
def test_registered_templates_create_reload_change_clear_and_creation_replay(signed, monkeypatch, product, first, second):
    client, service, identity, model = signed
    root = f'/api/products/{product}'
    catalog = client.get(root + '/templates')
    assert catalog.status_code == 200 and 'no-store' in catalog.headers['cache-control']
    items = catalog.json()['items']
    assert len(items) == 3 and all(x['domain'] == catalog.json()['domain'] for x in items)
    for item in items:
        assert item['context_fields'] and item['questions'] and item['pack_version'] == '1.3.0'
    body = {'creation_key': str(uuid4()), 'config': config(), 'template': {'id': first, 'version': '1.0.0'}}
    created = post(client, root + '/dossiers', body)
    assert created.status_code == 201, created.text
    doc = created.json()
    path = root + '/dossiers/' + doc['id']
    saved = doc['template']['selection']
    assert saved['id'] == first and saved['selected_at']
    assert doc['profile']['config'] == ProfileConfig.model_validate(body['config']).model_dump(mode='json')  # No silent question/source/default changes.
    definitions = dict(dossier_templates.TEMPLATES)
    definitions[first] = replace(definitions[first], version='2.0.0', title='Changed registry title')
    monkeypatch.setattr(dossier_templates, 'TEMPLATES', MappingProxyType(definitions))
    assert client.get(path).json()['template']['selection'] == saved
    assert post(client, root + '/dossiers', body).json()['id'] == doc['id']
    changed, update = choose(client, path, {'id': second, 'version': '1.0.0'})
    assert changed.status_code == 200, changed.text
    assert changed.json()['selection']['id'] == second
    assert put(client, path + '/template', update).json() == changed.json()
    assert post(client, root + '/dossiers', body).json()['template']['selection']['id'] == second
    assert post(client, root + '/dossiers', {**body, 'template': {'id': second, 'version': '1.0.0'}}).status_code == 409
    assert post(client, root + '/dossiers', {k: v for k, v in body.items() if k != 'template'}).status_code == 201
    assert client.get(path).json()['profile'] == doc['profile']
    assert client.get(path + '/domain-context').json()['saved'] is False
    assert client.get(path + '/export').json()['template_snapshot']['id'] == second
    assert saved['title'] in client.get(path + '/brief').text or changed.json()['selection']['title'] in client.get(path + '/brief').text
    cleared, _ = choose(client, path, None)
    assert cleared.status_code == 200 and not cleared.json()['saved']
    with service.db.session() as session:
        history = list(session.scalars(select(DossierEntry).where(DossierEntry.dossier_id == doc['id'],
                                                                 DossierEntry.kind == 'dossier_template').order_by(DossierEntry.created_at, DossierEntry.id)))
        assert len(history) == 3 and all(x.actor_user_id == identity['user']['id'] for x in history)
        assert history[0].data_json['template_after'] == saved
    assert model.calls == []


def test_invalid_wrong_domain_or_unavailable_template_never_creates_or_overwrites(signed):
    client, _, _, model = signed
    for template in [{'id': 'legal-question', 'version': '1.0.0'}, {'id': 'unknown', 'version': '1.0.0'},
                     {'id': 'market-access', 'version': '2.0.0'}, {'id': 'market-access'},
                     {'id': 'market-access', 'version': '1.0.0', 'title': 'Untrusted supplied guidance'}]:
        result = post(client, ROOT, {'creation_key': str(uuid4()), 'config': config(), 'template': template})
        assert result.status_code == 422, result.text
    assert client.get(ROOT).json()['total'] == 0
    doc, body = create(client)
    assert post(client, ROOT, {**body, 'template': {'id': 'market-access', 'version': '1.0.0'}}).status_code == 409
    root = ROOT + '/' + doc['id']
    result, _ = choose(client, root, {'id': 'legal-question', 'version': '1.0.0'})
    assert result.status_code == 422 and client.get(root).json()['work']['revision'] == 1
    assert model.calls == []


def test_stale_reused_csrf_and_future_format_fail_without_losing_original(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    result, body = choose(client, root, {'id': 'market-access', 'version': '1.0.0'})
    assert result.status_code == 200
    assert put(client, root + '/template', {**body, 'template': None}).status_code == 409
    assert put(client, root + '/template', {**body, 'request_key': str(uuid4())}).status_code == 409
    assert client.put(root + '/template', json={**body, 'expected_revision': 2}).status_code == 403
    with service.db.session() as session:
        row = session.get(ProductDossier, doc['id'])
        row.template_json = {**row.template_json, 'schema_id': 'dossier-template/future', 'title': '<script>retained</script>'}
        session.commit()
    current = client.get(root).json()
    assert current['template'] == {'saved': True, 'available': False, 'selection': None}
    assert client.get(root + '/brief').status_code == 200
    assert '<script>retained</script>' in client.get(root + '/export').json()['template_snapshot']['title']
    blocked, _ = choose(client, root, None)
    assert blocked.status_code == 409


@pytest.mark.parametrize('role', ['VIEWER', 'CONTRIBUTOR', 'EDITOR'])
def test_current_guest_roles_revocation_and_private_catalogue(signed, role):
    client, service, _, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    doc, root = managed(client)
    item = invitation(client, root, account, role)
    switch(client, cookies)
    accept(client, root, item)
    assert client.get('/api/products/pharma/templates').status_code == 200
    response, body = choose(client, root, {'id': 'market-access', 'version': '1.0.0'})
    assert response.status_code == (200 if role == 'EDITOR' else 403), response.text
    with service.db.session(include_all_organizations=True) as session:
        session.execute(delete(DossierMember).where(DossierMember.dossier_id == doc['id'],
                                                    DossierMember.user_id == account['user']['id']))
        session.commit()
    assert put(client, root + '/template', body).status_code == 404
    switch(client, owner)
    assert client.get(root).json()['template']['saved'] is (role == 'EDITOR')


def test_private_template_stays_out_of_public_reuse_and_escapes_print(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    result, body = choose(client, root, {'id': 'market-access', 'version': '1.0.0'})
    assert result.status_code == 200
    marker = 'PRIVATE-TEMPLATE<script>alert(1)</script>'
    with service.db.session() as session:
        row = session.get(ProductDossier, doc['id'])
        row.template_json = {**row.template_json, 'title': marker}
        session.commit()
    brief = client.get(root + '/brief')
    assert '&lt;script&gt;' in brief.text and '<script>alert' not in brief.text
    publication, _ = preview_and_publish(client, doc['id'])
    public = PUBLIC + '/' + publication['id']
    client.cookies.clear()
    assert marker not in client.get(public).text and marker not in client.get(PUBLIC).text
    assert client.get('/api/products/pharma/templates').status_code == 401
    assert client.put(root + '/template', json=body).status_code == 401
    assert _register(client, 'template-copy@example.ch').status_code == 201
    assert client.get(root).status_code == 404
    assert put(client, root + '/template', body).status_code == 404
    path, _, copy_body = prepare(client, public + '/discussion')
    copied = post(client, path, copy_body)
    assert copied.status_code == 201, copied.text
    assert not client.get(ROOT + '/' + copied.json()['dossier_id']).json()['template']['saved']
    assert model.calls == []


def test_template_migration_preserves_old_context_files_and_refuses_data_loss(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    original = client.post(root + '/files', headers=_csrf(client), files={'file': ('original.txt', b'Retained source')}).json()
    put(client, root + '/work', {'expected_revision': 1, 'context': {'subject': 'Preserved subject'}})
    with service.db.engine.connect() as connection:
        command.downgrade(migration_config(connection), '07d495bef125')
        command.upgrade(migration_config(connection), 'head')
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    assert client.get(root).json()['work']['context']['subject'] == 'Preserved subject'
    assert client.get(root + '/files/' + original['id']).content == b'Retained source'
    saved, _ = choose(client, root, {'id': 'market-access', 'version': '1.0.0'})
    assert saved.status_code == 200
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match='Retain saved templates'):
            command.downgrade(migration_config(connection), '07d495bef125')
    assert client.get(root).json()['template']['selection']['id'] == 'market-access'


def test_revoked_session_cannot_replay_a_saved_template(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    result, body = choose(client, root, {'id': 'market-access', 'version': '1.0.0'})
    assert result.status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        for login in session.scalars(select(UserSession).where(UserSession.user_id == identity['user']['id'])):
            login.revoked_at = utcnow()
        session.commit()
    assert client.get('/api/products/pharma/templates').status_code == 401
    assert put(client, root + '/template', body).status_code == 401
