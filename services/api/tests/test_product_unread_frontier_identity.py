"""Unread identities inform existing routing without becoming original evidence."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_retained_frontier import frontier as frontier

from helvetic_lens import product_iterative_research as research
from helvetic_lens import product_research_mission as mission
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.research_evidence_pack import POLICY, provider_input
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import DraftCheckpoint


def visible(session, run, branch):
    value = mission.context(session, run)
    return value, next(frontier for frontier in value['discovery_frontiers'] if frontier['branch_id'] == branch.id)


@pytest.mark.parametrize('status', ['failed', 'completed'])
def test_current_public_frontier_exposes_unread_identity_without_changing_sources_or_routing(frontier, status):
    session, run, branch, source, _ = frontier
    branch.status = status
    before, original = deepcopy(branch.checkpoint), deepcopy(source.snapshot)
    value, entry = visible(session, run, branch)
    assert entry['unread_candidates'] == [{'title': 'Original record', 'url': 'https://example.org/remaining'}]
    assert 'unread_candidates_omitted' not in entry
    assert value['unread_candidates_scope'] == mission.UNREAD_CANDIDATE_SCOPE
    assert 'untrusted' in value['unread_candidates_scope'] and 'not citable' in value['unread_candidates_scope']
    assert branch.id in mission.continuation_context(session, run)['frontiers']
    assert branch.checkpoint == before and source.snapshot == original
    assert set(entry) == {'branch_id', 'query', 'channels', 'remaining_candidates', 'pages_checked', 'unread_candidates'}


def test_legacy_filtering_is_current_and_independent_of_recovery_contract(frontier):
    session, run, branch, source, identity = frontier
    branch.status = 'completed'
    data = deepcopy(run.research_state)
    data['exploration'].pop('recovery_contract', None)
    run.research_state = data
    source.snapshot = {**source.snapshot, 'requested_url': 'https://example.org/requested',
        'redirect_chain': ['https://example.org/redirect']}
    state = deepcopy(branch.checkpoint)
    state['attempted_urls'].append('https://example.org/attempted')
    state['candidates'] += [
        {'url': url, 'title': 'Must be omitted'} for url in [source.url, 'https://example.org/requested',
            'https://example.org/redirect', 'https://example.org/attempted', 'https://example.org/excluded']]
    state['candidates'] += [
        {'url': 'https://EXAMPLE.org:443/remaining#anchor', 'title': 'Duplicate normalized identity'},
        {'url': 'https://example.org/new', 'title': '<b> Public &amp; original </b>\n record',
            'summary': 'PRIVATE SNIPPET MUST NOT APPEAR', 'provider': 'PRIVATE PROVIDER',
            'cursor': 'PRIVATE CURSOR', 'citation_ref': 999},
        {'url': 'https://user:password@example.org/secret', 'title': 'Credentials'},
        {'url': 'https://127.0.0.1/private', 'title': 'Private address'},
        {'url': 'https://example.internal/private', 'title': 'Internal address'},
        {'url': 'file:///private/source', 'title': 'Local file'},
        {'url': None, 'title': 'Missing URL'}, {'url': 'https://example.org/bad-title', 'title': {}}, None]
    branch.checkpoint = state
    session.add(DossierEntry(dossier_id=run.dossier_id, organization_id=run.organization_id,
        request_key=str(uuid4()), kind='source_review', actor_user_id=identity['user']['id'],
        url='https://EXAMPLE.org:443/excluded#section', body='Private exclusion reason.',
        data_json={'decision': 'exclude', 'revision': 1}))
    session.flush()
    before = deepcopy(branch.checkpoint)
    value, entry = visible(session, run, branch)
    assert entry['unread_candidates'] == [
        {'title': 'Original record', 'url': 'https://example.org/remaining'},
        {'title': 'Public & original record', 'url': 'https://example.org/new'}]
    assert 'unread_candidates_omitted' not in entry, 'Filtered/malformed/duplicate records are not eligible omissions'
    assert 'PRIVATE' not in json.dumps(value) and 'password' not in json.dumps(value)
    assert branch.checkpoint == before
    # A new exclusion takes effect on the next projection without changing the
    # completed legacy branch's eligibility or retained candidate list.
    session.add(DossierEntry(dossier_id=run.dossier_id, organization_id=run.organization_id,
        request_key=str(uuid4()), kind='source_review', actor_user_id=identity['user']['id'],
        url='https://example.org/new', body='Private updated exclusion.', data_json={'decision': 'exclude', 'revision': 1}))
    session.flush()
    assert visible(session, run, branch)[1]['unread_candidates'] == entry['unread_candidates'][:1]
    assert mission.discovery_frontier_available(session, run, branch)


def test_private_or_unowned_branch_metadata_is_omitted_with_legacy_shape_unchanged(frontier):
    session, run, branch, _, _ = frontier
    branch.status = 'completed'
    base = deepcopy(branch.checkpoint)
    baseline = None
    for private_key in ('saved', 'research_control', 'contribution_entry_id', 'public_file_id', 'file', 'recurring_web'):
        branch.checkpoint = {**deepcopy(base), private_key: 'PRIVATE SENTINEL'}
        value, entry = visible(session, run, branch)
        assert 'unread_candidates' not in entry and 'unread_candidates_scope' not in value
        assert 'PRIVATE SENTINEL' not in json.dumps(value)
        serialized = json.dumps(value, ensure_ascii=False)
        baseline = serialized if baseline is None else baseline
        assert serialized == baseline
    for question_id in ('unknown-question', None):
        branch.checkpoint = {**deepcopy(base), 'question_id': question_id}
        assert json.dumps(visible(session, run, branch)[0], ensure_ascii=False) == baseline
    branch.checkpoint = base
    run.external_discovery = False
    assert json.dumps(visible(session, run, branch)[0], ensure_ascii=False) == baseline


def test_metadata_view_bound_preserves_all_candidates_and_reports_exact_eligible_omissions(frontier):
    session, run, branch, _, _ = frontier
    branch.status = 'completed'
    question_id = research.add_question(session, run, research.BranchDraft(question='Which other original resolves the condition?',
        query='additional original condition', purpose='Read another original.', priority=2))
    research.schedule_questions(session, run)
    question = next(q for q in run.research_state['questions'] if q['id'] == question_id)
    other = session.get(InvestigationBranch, question['branch_id'])
    other.status = 'completed'
    for current, label in ((branch, 'first'), (other, 'second')):
        current.checkpoint = {**current.checkpoint, 'gate_index': 0,
            'candidates': [{'title': f'Original identity {label} {index}',
                'url': f'https://example.org/{label}/{index}'} for index in range(100)]}
    saved = [deepcopy(current.checkpoint) for current in (branch, other)]
    value = mission.context(session, run)
    entries = [entry for entry in value['discovery_frontiers'] if entry['branch_id'] in {branch.id, other.id}]
    total_cost = sum(len(json.dumps(entry['unread_candidates'], ensure_ascii=False))
        for entry in entries if 'unread_candidates' in entry)
    assert total_cost <= mission.UNREAD_CANDIDATE_CHARACTERS
    assert sum(len(entry.get('unread_candidates', [])) for entry in entries) > 12, 'No small candidate-count cap'
    assert sum(entry.get('unread_candidates_omitted', 0) for entry in entries) > 0
    for current, entry, before in zip((branch, other), entries, saved, strict=True):
        shown = entry.get('unread_candidates', [])
        assert len(shown) + entry.get('unread_candidates_omitted', 0) == 100
        assert 'unread_candidates' not in entry or shown, 'No unaccounted empty lists after allowance exhaustion'
        assert shown == [{'title': item['title'], 'url': item['url']}
            for item in current.checkpoint['candidates'][:len(shown)]]
        assert current.checkpoint == before


def test_identity_reaches_real_provider_transport_and_invalidates_only_changed_request_cache(frontier):
    session, run, branch, source, _ = frontier
    def wire():
        return EvidenceWire({'phase': 'brief', 'run_id': run.id, 'input': {'original_question': run.question,
            'research_mission': mission.context(session, run), 'sources': [{'id': source.id,
                'kind': source.kind, 'sha256': source.sha256, 'title': source.title,
                'url': source.url, 'excerpts': deepcopy(source.snapshot['excerpts'])}]}},
            mission.schema(Briefing), '', shared_answer=True)
    current = wire()
    packet = provider_input(current, current.references)
    assert packet['research_mission']['discovery_frontiers'][0]['unread_candidates'] == [
        {'title': 'Original record', 'url': 'https://example.org/remaining'}]
    assert packet['research_mission']['unread_candidates_scope'] == mission.UNREAD_CANDIDATE_SCOPE
    assert all(ref['source_id'] == source.id and ref['quote'] == source.snapshot['excerpts'][0]['text']
        for ref in current.references.values())
    assert 'https://example.org/remaining' not in json.dumps(packet['sources'])
    originals = deepcopy(current.references)
    settings, saved = Settings(_env_file=None), {}
    def checkpoint(wire, work):
        return DraftCheckpoint(work, settings, wire.system, 'existing-review', wire.schema,
            json.dumps(wire.input, ensure_ascii=False), {}, preparation_policy=POLICY)
    first = checkpoint(current, saved)
    first.bind_request(current.schema, json.dumps(packet, ensure_ascii=False))
    first.save('finalizing', 'PRIVATE CANDIDATE', [], {})
    restored = checkpoint(wire(), json.loads(json.dumps(saved)))
    restored.bind_request(current.schema, json.dumps(packet, ensure_ascii=False))
    assert restored.value['raw'] == 'PRIVATE CANDIDATE'
    state = deepcopy(branch.checkpoint)
    state['candidates'][1]['summary'] = 'Changed raw snippet remains private.'
    branch.checkpoint = state
    same = wire()
    assert same.receipt == current.receipt and provider_input(same, same.references) == packet
    assert checkpoint(same, deepcopy(saved)).value is not None
    state = deepcopy(branch.checkpoint)
    state['candidates'][1]['title'] = 'A newly identified original record'
    branch.checkpoint = state
    changed = wire()
    assert changed.references == originals and changed.schema == current.schema
    assert changed.receipt['input_fingerprint'] != current.receipt['input_fingerprint']
    assert checkpoint(changed, deepcopy(saved)).value is None
    assert 'PRIVATE CANDIDATE' not in json.dumps(provider_input(changed, changed.references))
