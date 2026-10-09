"""Typed subject details preserve old workflows, audit and current audience."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_account_deletion_migration import config as migration_config
from test_auth import _csrf, _register
from test_legal_profiles import config
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_operations import put
from test_product_publications import PUBLIC, preview_and_publish
from test_product_reuse import prepare
from test_product_teams import managed, switch

from alembic import command
from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import User, UserSession
from helvetic_lens.product_domain_context import validated
from helvetic_lens.product_models import DossierEntry, DossierMember, ProductDossier


def update(client, root, values, **changes):
    current = client.get(root + '/domain-context').json()
    body = {'expected_revision': current['revision'], 'request_key': str(uuid4()),
            'schema_id': current['schema_id'], 'values': values, **changes}
    return put(client, root + '/domain-context', body), body


@pytest.mark.parametrize('product', ['pharma', 'legal', 'loyer'])
def test_empty_and_normalized_unchanged_saves_preserve_history_and_real_clear(signed, product):
    client, service, _, model = signed
    created = post(client, f'/api/products/{product}/dossiers',
                   {'creation_key': str(uuid4()), 'config': config()}).json()
    root = f'/api/products/{product}/dossiers/{created["id"]}'
    initial = client.get(root + '/domain-context').json()
    field = 'product_names' if product == 'pharma' else 'parties'

    def history():
        with service.db.session() as session:
            return list(session.scalars(select(DossierEntry).where(
                DossierEntry.dossier_id == created['id'], DossierEntry.kind == 'domain_context')))

    # Opening an optional form and pressing save does not create an apparent update.
    empty, empty_body = update(client, root, {})
    assert empty.status_code == 200 and empty.json() == initial
    assert put(client, root + '/domain-context', empty_body).json() == initial
    explicit_empty, _ = update(client, root, initial['values'])
    assert explicit_empty.json() == initial and history() == []
    with service.db.session() as session:
        assert session.get(ProductDossier, created['id']).domain_context_json == {}

    changed, changed_body = update(client, root, {field: ['Name A', 'Name B']})
    assert changed.status_code == 200 and changed.json()['revision'] == initial['revision'] + 1
    saved = changed.json()
    unchanged, _ = update(client, root, {field: [' Name A ', 'Name A', 'Name B ']})
    assert unchanged.status_code == 200 and unchanged.json() == saved
    assert len(history()) == 1
    # Equality must not bypass a concurrent change or allow an old blank request to erase it.
    assert put(client, root + '/domain-context', empty_body).status_code == 409
    stale, _ = update(client, root, saved['values'], expected_revision=initial['revision'])
    assert stale.status_code == 409

    cleared, clear_body = update(client, root, {})
    cleared_payload = cleared.json()
    assert cleared.status_code == 200 and cleared_payload['revision'] == saved['revision'] + 1
    assert cleared_payload['saved'] and cleared_payload['updated_at']
    assert all(not value for value in cleared_payload['values'].values())
    assert len(history()) == 2
    clear_entry = next(entry for entry in history() if entry.data_json['revision'] == cleared_payload['revision'])
    assert clear_entry.data_json['before']['values'] == saved['values']
    assert clear_entry.data_json['after']['values'] == cleared_payload['values']
    assert put(client, root + '/domain-context', clear_body).json() == cleared_payload
    assert update(client, root, {})[0].json() == cleared_payload
    # A recorded successful write still replays without restoring its old values.
    assert put(client, root + '/domain-context', changed_body).json() == cleared_payload
    assert len(history()) == 2 and model.calls == []


def test_legacy_empty_snapshot_is_retained_without_another_fake_update(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    current = client.get(root + '/domain-context').json()
    legacy = {key: current[key] for key in ['domain', 'pack_id', 'pack_version', 'schema_id', 'values']}
    legacy['updated_at'] = '2026-09-28T12:00:00+00:00'
    with service.db.session() as session:
        row = session.get(ProductDossier, doc['id'])
        row.domain_context_json = legacy
        session.commit()
    before = client.get(root + '/domain-context').json()
    result, _ = update(client, root, {})
    assert result.status_code == 200 and result.json() == before
    assert before['saved'] and before['updated_at'] == legacy['updated_at']
    with service.db.session() as session:
        assert session.get(ProductDossier, doc['id']).domain_context_json == legacy
        assert session.scalar(select(DossierEntry).where(
            DossierEntry.dossier_id == doc['id'], DossierEntry.kind == 'domain_context')) is None


@pytest.mark.parametrize('product', ['pharma', 'legal', 'loyer'])
def test_optional_typed_context_roundtrip_clear_audit_and_old_work_compatibility(signed, product):
    client, service, identity, model = signed
    created = post(client, f'/api/products/{product}/dossiers',
                   {'creation_key': str(uuid4()), 'config': config()})
    assert created.status_code == 201, created.text
    doc = created.json()
    root = f'/api/products/{product}/dossiers/{doc["id"]}'
    empty = client.get(root + '/domain-context').json()
    assert empty['saved'] is False and empty['revision'] == 1
    assert empty['pack_version'] == '2.0.0'
    values = ({'product_names': [' Brand A ', 'Brand A'], 'active_substances': ['Substance A'],
               'countries': ['Switzerland'], 'indications': ['Recorded indication']}
              if product == 'pharma' else {'jurisdictions': ['Basel-Stadt'], 'parties': ['Party A'],
                                          'procedural_stage': 'Recorded stage', 'relevant_dates': ['2026-09-28']})
    result, body = update(client, root, values)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['saved'] and saved['revision'] == 2 and saved['updated_at']
    assert client.get(root + '/domain-context').json() == saved
    assert put(client, root + '/domain-context', body).json() == saved  # exact retry
    assert put(client, root + '/domain-context', {**body, 'values': {}}).status_code == 409
    assert put(client, root + '/domain-context', {**body, 'request_key': str(uuid4())}).status_code == 409
    if product == 'pharma':
        assert saved['values']['product_names'] == ['Brand A']
        assert saved['values']['active_substances'] == ['Substance A']
    # The old strict work form still saves independently, with the shared revision fence.
    work = put(client, root + '/work', {'expected_revision': 2, 'context': {'subject': 'Old client subject'}})
    assert work.status_code == 200, work.text
    assert client.get(root + '/domain-context').json()['values'] == saved['values']
    assert client.get(root + '/export').json()['domain_context']['values'] == saved['values']
    with service.db.session() as session:
        entries = list(session.scalars(select(DossierEntry).where(DossierEntry.dossier_id == doc['id'],
                                                                 DossierEntry.kind == 'domain_context')))
        assert len(entries) == 1 and entries[0].actor_user_id == identity['user']['id']
        assert entries[0].data_json['before'] == {}
        assert entries[0].data_json['after']['values'] == saved['values']
    cleared, _ = update(client, root, {})
    assert cleared.status_code == 200 and all(not v for v in cleared.json()['values'].values())
    assert client.get(root).json()['work']['context']['subject'] == 'Old client subject'
    assert model.calls == []  # Saving subject fields never infers or searches.


@pytest.mark.parametrize('schema,values', [
    ('pharma-context/v1', {'laws': ['Wrong domain']}),
    ('legal-context/v1', {'active_substances': ['Wrong domain']}),
    ('pharma-context/v1', {'product_names': 'Not a list'}),
    ('pharma-context/v1', {'product_names': [3]}),
    ('pharma-context/v1', {'product_names': ['  ']}),
    ('pharma-context/v1', {'product_names': ['x' * 241]}),
    ('pharma-context/v1', {'product_names': [str(i) for i in range(31)]}),
    ('legal-context/v1', {'relevant_dates': ['2026-02-30']}),
    ('legal-context/v1', {'relevant_dates': ['20260928']}),
    ('legal-context/v1', {'procedural_stage': ['Not text']}),
    ('pharma-context/v1', {key: [str(i).ljust(240, 'x') for i in range(30)]
                          for key in ['product_names', 'active_substances']}),
])
def test_invalid_context_rejects_unknown_fields_types_bounds_and_impossible_dates(schema, values):
    with pytest.raises(DomainError):
        validated(schema, values)


def test_private_context_never_enters_public_projection_or_reused_copy_and_print_is_escaped(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    marker = 'PRIVATE-SUBJECT<script>alert(1)</script>'
    saved, _ = update(client, root, {'product_names': [marker]})
    assert saved.status_code == 200
    brief = client.get(root + '/brief')
    assert brief.status_code == 200 and '&lt;script&gt;' in brief.text and '<script>alert' not in brief.text
    assert 'User-provided context' in brief.text and 'no-store' in brief.headers['cache-control']
    publication, _ = preview_and_publish(client, doc['id'])
    public = PUBLIC + '/' + publication['id']
    client.cookies.clear()
    assert marker not in client.get(public).text and marker not in client.get(PUBLIC).text
    assert client.get(root + '/domain-context').status_code == 401
    assert _register(client, 'context-copy@example.ch').status_code == 201
    assert client.get(root + '/domain-context').status_code == 404
    path, _, body = prepare(client, public + '/discussion')
    copied = post(client, path, body)
    assert copied.status_code == 201, copied.text
    copy_root = ROOT + '/' + copied.json()['dossier_id']
    assert client.get(copy_root + '/domain-context').json()['saved'] is False
    assert marker not in client.get(copy_root + '/export').text
    assert model.calls == []


@pytest.mark.parametrize('role', ['VIEWER', 'CONTRIBUTOR', 'EDITOR'])
def test_current_guest_roles_and_revocation_fence_reads_writes_and_replays(signed, role):
    client, service, _, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    doc, root = managed(client)
    item = invitation(client, root, account, role)
    switch(client, cookies)
    accept(client, root, item)
    assert client.get(root + '/domain-context').status_code == 200
    empty, _ = update(client, root, {})
    assert empty.status_code == (200 if role == 'EDITOR' else 403), empty.text
    result, body = update(client, root, {'product_names': ['Guest recorded name']})
    assert result.status_code == (200 if role == 'EDITOR' else 403), result.text
    with service.db.session(include_all_organizations=True) as session:
        session.execute(delete(DossierMember).where(DossierMember.dossier_id == doc['id'],
                                                    DossierMember.user_id == account['user']['id']))
        session.commit()
    assert client.get(root + '/domain-context').status_code == 404
    assert put(client, root + '/domain-context', body).status_code == 404
    switch(client, owner)
    assert client.get(root + '/domain-context').json()['saved'] is (role == 'EDITOR')


def test_schema_mismatch_unknown_saved_schema_and_csrf_never_overwrite_retained_data(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    result, body = update(client, root, {'product_names': ['Retained']})
    assert result.status_code == 200
    assert client.put(root + '/domain-context', json={**body, 'expected_revision': 2}).status_code == 403
    assert put(client, root + '/domain-context', {**body, 'schema_id': 'legal-context/v1'}).status_code == 409
    with service.db.session() as session:
        row = session.get(ProductDossier, doc['id'])
        row.domain_context_json = {**row.domain_context_json, 'schema_id': 'pharma-context/future'}
        session.commit()
    assert client.get(root + '/domain-context').status_code == 409
    assert client.get(root).status_code == 200
    assert client.get(root + '/brief').status_code == 200
    assert client.get(root + '/export').json()['domain_context']['values']['product_names'] == ['Retained']
    assert put(client, root + '/domain-context', {**body, 'expected_revision': 2}).status_code == 409


def test_additive_migration_preserves_legacy_data_and_refuses_destructive_context_downgrade(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    original = client.post(root + '/files', headers=_csrf(client), files={'file': ('kept.txt', b'Original retained bytes')}).json()
    assert put(client, root + '/work', {'expected_revision': 1, 'context': {'subject': 'Legacy context'}}).status_code == 200
    with service.db.engine.connect() as connection:
        command.downgrade(migration_config(connection), '06d495bef125')
        assert connection.exec_driver_sql('SELECT count(*) FROM product_dossier_entries').scalar() == 2
        command.upgrade(migration_config(connection), 'head')
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    assert client.get(root).json()['work']['context']['subject'] == 'Legacy context'
    assert client.get(root + '/domain-context').json()['saved'] is False
    assert client.get(root + '/files/' + original['id']).content == b'Original retained bytes'
    saved, _ = update(client, root, {'product_names': ['Persisted new context']})
    assert saved.status_code == 200
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match='Retain saved domain context'):
            command.downgrade(migration_config(connection), '06d495bef125')
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    assert client.get(root + '/domain-context').json()['values']['product_names'] == ['Persisted new context']


def test_revoked_session_cannot_read_change_or_replay_context(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    root = ROOT + '/' + doc['id']
    saved, body = update(client, root, {'product_names': ['Retained context']})
    assert saved.status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        for login in session.scalars(select(UserSession).where(UserSession.user_id == identity['user']['id'])):
            login.revoked_at = utcnow()
        session.commit()
    assert client.get(root + '/domain-context').status_code == 401
    assert put(client, root + '/domain-context', body).status_code == 401
    with service.db.session() as session:
        assert session.get(ProductDossier, doc['id']).domain_context_json['values']['product_names'] == ['Retained context']


def test_erasure_removes_private_subject_and_detaches_shared_audit_author(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    active(client, shared)
    for doc in [private, shared]:
        saved, _ = update(client, ROOT + '/' + doc['id'], {'product_names': ['Recorded context']})
        assert saved.status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, identity['user']['id'])
        erase_selected(session, user, select_private_rows(session, user, []))
        session.commit()
    with service.db.session() as session:
        assert session.get(ProductDossier, private['id']) is None
        assert session.get(ProductDossier, shared['id']).domain_context_json['values']['product_names'] == ['Recorded context']
        entry = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == shared['id'],
                                                          DossierEntry.kind == 'domain_context'))
        assert entry.actor_user_id is None
        assert 'Ada Example' not in str(entry.data_json)
