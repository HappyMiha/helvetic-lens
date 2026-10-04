"""Exact selected packets resume without measuring every original again."""
import json
from copy import deepcopy

import pytest
from test_research_evidence_pack import Selector, corpus, ranking, service

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_evidence_pack as pack
from helvetic_lens.config import DomainError


def envelope(wire):
    return {'projection': 'provider_input', 'system': wire.system,
        'payload': {key: value for key, value in wire.input.items() if key != 'sources'},
        'schema': wire.schema, 'provider': None}


def fixture(monkeypatch):
    wire, checkpoints = corpus(20), {}
    wire.references[21] = {'source_id': 's1', 'locator': 'p2',
        'quote': 'This exact exception qualifies the first original.'}
    calls, checks = [], []
    original = pack._final_size

    def measure(current, references, **options):
        calls.append(tuple(references))
        return original(current, references, **options)

    async def current(*args):
        checks.append(True)

    monkeypatch.setattr(pack, '_final_size', measure)
    monkeypatch.setattr(retrieval, 'ensure_current', current)
    ranked = ranking(monkeypatch)
    return wire, checkpoints, service(Selector(None)), calls, checks, ranked


@pytest.mark.asyncio
async def test_bound_saved_packet_revalidates_only_mandatory_and_selected_with_fresh_access(monkeypatch):
    wire, checkpoints, current, calls, checks, ranked = fixture(monkeypatch)
    before = deepcopy(wire.__dict__)
    first = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    assert {1, 21} <= set(first) and len(first) < len(wire.references)
    assert len(calls) > 20 and len(ranked) == len(checks) == 1
    checkpoints = json.loads(json.dumps(checkpoints))
    saved_before = deepcopy(checkpoints)
    calls.clear()
    progress = []
    second = await pack.select_evidence(current, wire, wire.input['original_question'], 0,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire),
        on_progress=lambda: progress.append(True))
    assert second == first and second is not first
    assert calls == [(1, 21), tuple(first)]
    assert len(ranked) == 1 and len(checks) == 2 and progress == []
    assert checkpoints == saved_before and wire.__dict__ == before


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['prompt', 'payload', 'schema', 'provider', 'allowance',
    'source', 'required', 'source_context', 'work_scope', 'input_metadata', 'source_use', 'policy'])
async def test_bound_cache_requires_the_current_full_envelope_and_structural_scope(monkeypatch, changed):
    wire, checkpoints, current, calls, _, ranked = fixture(monkeypatch)
    binding = deepcopy(envelope(wire))
    await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=binding)
    required = (1,)
    if changed == 'prompt':
        binding['system'] = binding['system'].replace('answer', 'result')  # Same length is not identity.
    elif changed == 'payload':
        binding['payload']['correction_target'] = {'previous_statement': 'A different assertion.'}
    elif changed == 'schema':
        binding['schema']['description'] = 'A different complete output contract.'
    elif changed == 'provider':
        binding['provider'] = 'another-adapter'
    elif changed == 'allowance':
        current.settings.apertus_context_chars += 1
    elif changed == 'source':
        wire.input['sources'][-1]['sha256'] = 'a-new-uncited-original'
    elif changed == 'required':
        required = (1, 2)
    elif changed == 'source_context':
        wire.source_context = [{'observation_refs': [1], 'anchors': [
            {'kind': 'condition', 'citation_refs': [2]}]}]
    elif changed == 'work_scope':
        wire.work = {'phase': 'brief', 'run_id': 'another-current-run', 'generation': 2}
    elif changed == 'input_metadata':
        wire.input['research_mission'] = {'unvalidated_proposals': ['An unresolved proposal.']}
    elif changed == 'source_use':
        wire.reference_uses = {2: 'reference_metadata'}
    else:
        monkeypatch.setattr(pack, 'POLICY', 'a-different-existing-packing-policy')
    calls.clear()
    await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=required, envelope_binding=binding)
    assert len(calls) > 2 and len(ranked) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['lost_context', 'duplicate_id', 'foreign_id', 'unit', 'lost_mandatory'])
async def test_bound_hit_never_trusts_damaged_selection_or_unit_closure(monkeypatch, damage):
    wire, checkpoints, current, calls, _, ranked = fixture(monkeypatch)
    first = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    saved = next(iter(checkpoints['evidence_selection'].values()))
    if damage == 'lost_context':
        saved['selected'].remove(21)
    elif damage == 'duplicate_id':
        saved['selected'].append(saved['selected'][0])
    elif damage == 'foreign_id':
        saved['selected'].append(9999)
    elif damage == 'unit':
        saved['selected_units'].append(9999)
    else:
        saved['selected'] = [2]
        saved['selected_units'] = [1]
    calls.clear()
    second = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    assert first == second and len(ranked) == 2 and len(calls) > 2


@pytest.mark.asyncio
async def test_legacy_receipt_is_validated_then_enriched_without_a_new_selection_or_progress_node(monkeypatch):
    from helvetic_lens.research_synthesis_resume import completed_work, made_progress

    wire, checkpoints, current, calls, _, ranked = fixture(monkeypatch)
    first = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,))
    nodes = set(checkpoints['evidence_selection'])
    completed = completed_work({'parts': checkpoints})
    assert all('envelope_fingerprint' not in saved for saved in checkpoints['evidence_selection'].values())
    calls.clear()
    second = await pack.select_evidence(current, wire, wire.input['original_question'], 0,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    assert second == first and len(ranked) == 1 and len(calls) > 20
    assert set(checkpoints['evidence_selection']) == nodes
    assert completed_work({'parts': checkpoints}) == completed
    assert not made_progress(completed, completed_work({'parts': checkpoints}))
    calls.clear()
    third = await pack.select_evidence(current, wire, wire.input['original_question'], 0,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    assert third == first and len(ranked) == 1 and len(calls) == 2
    calls.clear()
    # A custom/unbound caller still measures its current envelope conservatively.
    await pack.select_evidence(current, wire, wire.input['original_question'], 0,
        checkpoints=checkpoints, required_refs=(1,))
    assert len(calls) > 20 and len(ranked) == 1


@pytest.mark.asyncio
async def test_bound_cache_still_rejects_current_access_withdrawal(monkeypatch):
    wire, checkpoints, current, calls, _, ranked = fixture(monkeypatch)
    await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))

    async def withdrawn(*args):
        raise DomainError('Current source access was withdrawn.', 409, 'evidence_changed')

    monkeypatch.setattr(retrieval, 'ensure_current', withdrawn)
    calls.clear()
    with pytest.raises(DomainError) as caught:
        await pack.select_evidence(current, wire, wire.input['original_question'], 0,
            checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire))
    assert caught.value.code == 'evidence_changed' and len(calls) == 2 and len(ranked) == 1


@pytest.mark.asyncio
async def test_bound_cache_rechecks_actual_packet_fit_even_if_a_callback_contract_is_stale(monkeypatch):
    wire, checkpoints, current, _, _, ranked = fixture(monkeypatch)
    limit, measured = 3, []

    def fits(references):
        measured.append(tuple(references))
        return len(references) <= limit

    first = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire), fits=fits)
    assert len(first) == 3
    limit = 2  # Even an incorrectly unchanged caller binding cannot bypass actual fit.
    measured.clear()
    second = await pack.select_evidence(current, wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, required_refs=(1,), envelope_binding=envelope(wire), fits=fits)
    assert tuple(first) in measured and set(second) == {1, 21} and len(ranked) == 2


@pytest.mark.asyncio
async def test_requested_answer_caller_binds_its_actual_writer_contract(monkeypatch):
    from helvetic_lens.research_answer_parts import answer_request

    wire = corpus(100, 'The permit remains valid until the stated date. ' * 8)
    checkpoints, calls = {}, []
    ranked = ranking(monkeypatch)

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            assert 'points' in options['response_schema']['properties']
            return json.dumps({'points': [{'statement': 'The permit remains valid until the stated date.',
                'evidence': [{'citation_ref': 1, 'role': 'support'}]}], 'remaining_gap': ''})

    current = service(Model(), 16000)
    points, gap, _ = await answer_request(current, wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert len(points) == 1 and not gap and len(ranked) == len(calls) == 1
    assert all(node.get('envelope_fingerprint') for node in checkpoints['evidence_selection'].values())
    await answer_request(current, wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(checkpoints)))
    assert len(ranked) == len(calls) == 1
