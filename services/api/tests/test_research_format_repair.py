"""Bound real repair packets and resume work; scripted outputs do not prove truth."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_answer_review, research_final_coverage, research_final_review
from helvetic_lens import research_evidence_pack as pack
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire, WireError, clarification_errors
from helvetic_lens.research_original_context import reference_units
from helvetic_lens.research_synthesis_resume import KEY, DraftCheckpoint, completed_work


def setup(monkeypatch):
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Explain permitted use and distribution requirements.', 'research_mission': {},
        'sources': [{'id': letter * 36, 'kind': 'public_source', 'sha256': letter * 64,
            'url': f'https://example.test/{letter}', 'excerpts': [{'passage': 'p1',
                'text': f'The {letter} register describes permitted use and distribution. ' + 'Complete original qualification. ' * 22}]}
            for letter in 'abcd']}}
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '')
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    service = SimpleNamespace(settings=settings, model_client=ModelClient(settings))

    async def rank(service, wire, question, seconds, **kwargs):
        return {'rankings': [{'query': question, 'references': list(wire.references)}],
            'coverage': {'method': 'scripted_order', 'semantic_status': 'not_assessed'}}

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    return service, work, schema, wire


def answer(wire, references=None, action='finish'):
    refs = references or wire.references
    key = next(iter(refs))
    return {'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
        {'statement': refs[key]['quote'], 'evidence': [{'citation_ref': key, 'role': 'support'}]}]},
        'next_action': action}


def checkpoint(service, work, wire):
    return DraftCheckpoint(work, service.settings, wire.system, gateway.ANSWER_WORKFLOW, wire.schema,
        json.dumps(wire.input, ensure_ascii=False), {'max_output_tokens': 4096}, preparation_policy=pack.POLICY)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['validation_feedback', 'error_only', 'repacked_error_only'])
async def test_repairs_keep_exact_errors_and_whole_originals_within_actual_envelope(monkeypatch, mode):
    service, work, schema, wire = setup(monkeypatch)
    original = deepcopy(work['input'])
    invalid = json.dumps(answer(wire, action='clarify'))
    errors = clarification_errors(json.loads(invalid))
    node = {'errors': errors, 'mode': 'error_only'}
    error_system, error_payload, error_schema = gateway._repair_request(wire, wire.system, wire.references, node)
    error_size = pack.request_characters(error_system, error_payload, error_schema, provider='swisscom')
    base_size = pack.request_characters(wire.system, pack.provider_input(wire, wire.references),
        pack.bounded_schema(wire.schema, wire.references), provider='swisscom')
    service.settings.apertus_context_chars = {'validation_feedback': 96000,
        'error_only': error_size, 'repacked_error_only': base_size + 1}[mode]
    resume = checkpoint(service, work, wire)
    resume.parts['final_reviews'] = {'clauses:discarded-draft': {'overall': {'verdict': 'supported'}}}
    vectors = {'exact-source-bound': {'documents': [], 'vectors': []}}
    resume.parts['active_retrieval_vectors'] = deepcopy(vectors)
    resume.save('draft', invalid, [], {})
    prompt, payload, bounded, selected = await gateway.prepare_format_repair(
        service, wire, wire.system, wire.references, errors, invalid, [], 90, resume)
    assert resume.parts['format_repair']['mode'] == mode
    assert json.dumps(errors) in prompt and prompt != wire.system
    assert pack.request_characters(prompt, payload, bounded, provider='swisscom') <= service.settings.apertus_context_chars
    assert set(selected) < set(wire.references) if mode == 'repacked_error_only' else selected == wire.references
    assert set(selected) == {key for unit in reference_units(wire)
        if set(unit['references']) <= set(selected) for key in unit['references']}
    original_payload = payload.get('original_evidence', payload)
    assert original_payload['original_question'] == original['original_question']
    assert {p['citation_ref'] for source in original_payload['sources'] for p in source['excerpts']
        if 'citation_ref' in p} == set(selected)
    assert work['input'] == original and resume.value['stage'] == 'preparing' and resume.value['raw'] == ''
    assert 'final_reviews' not in resume.parts
    assert resume.parts['active_retrieval_vectors'] == vectors
    assert not completed_work({'parts': {'format_repair': resume.parts['format_repair']}})
    again = checkpoint(service, json.loads(json.dumps(work)), wire)
    restored = await gateway.restore_format_repair(service, wire, wire.system, again, 90)
    assert restored == (prompt, payload, bounded, selected)
    assert again.request_binding == fingerprint({'system': prompt, 'schema': bounded,
        'content': json.dumps(payload, ensure_ascii=False)})


@pytest.mark.asyncio
async def test_feedback_metadata_that_cannot_fit_never_drops_errors(monkeypatch):
    service, work, schema, wire = setup(monkeypatch)
    resume = checkpoint(service, work, wire)
    error = {'path': ['large_field'], 'reason': 'Exact validation diagnostic. ' * 1500}
    with pytest.raises(DomainError) as caught:
        await gateway.prepare_format_repair(service, wire, wire.system, wire.references,
            [error], '{}', [], 90, resume)
    assert caught.value.code == 'research_evidence_group_too_large'
    assert resume.parts['format_repair']['errors'] == [error]
    assert resume.value['stage'] == 'preparing' and resume.value['raw'] == ''


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['errors', 'access'])
async def test_restored_repair_requires_unchanged_feedback_and_fresh_access(monkeypatch, changed):
    service, work, schema, wire = setup(monkeypatch)
    resume = checkpoint(service, work, wire)
    await gateway.prepare_format_repair(service, wire, wire.system, wire.references,
        [{'path': ['clarification'], 'reason': 'Supply a cited choice.'}], '{}', [], 90, resume)
    if changed == 'errors':
        resume.parts['format_repair']['errors'][0]['reason'] = 'A different required correction.'
    else:
        async def denied(*args):
            raise DomainError('Access changed', 409, 'invalid_evidence')
        monkeypatch.setattr(retrieval, 'ensure_current', denied)
    with pytest.raises(ValueError if changed == 'errors' else DomainError):
        await gateway.restore_format_repair(service, wire, wire.system, resume, 90)


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['source', 'question', 'provider', 'schema'])
async def test_repair_descriptor_does_not_override_base_binding(monkeypatch, change):
    service, work, schema, wire = setup(monkeypatch)
    resume = checkpoint(service, work, wire)
    await gateway.prepare_format_repair(service, wire, wire.system, wire.references,
        [{'path': ['clarification'], 'reason': 'Supply a cited choice.'}], '{}', [], 90, resume)
    resume.save('finalizing', json.dumps(answer(wire)), [], {})
    current = json.loads(json.dumps(work))
    if change == 'source':
        current['input']['sources'][0]['excerpts'][0]['text'] = 'The current original differs.'
    elif change == 'question':
        current['input']['original_question'] = 'Explain the filing procedure.'
    elif change == 'provider':
        service.settings.apertus_model = 'another-serving-model'
    changed_wire = EvidenceWire(current, schema, '')
    if change == 'schema':
        changed_wire.schema['properties']['next_action']['anyOf'][1]['properties']['clarification']['maxLength'] = 299
    changed_resume = checkpoint(service, current, changed_wire)
    assert changed_resume.value is None and not changed_resume.parts


@pytest.mark.asyncio
@pytest.mark.parametrize('malformed_resumed_repair', [False, True])
async def test_gateway_resumes_actual_repair_before_ordinary_pack_and_retains_final_checks(monkeypatch, malformed_resumed_repair):
    service, work, schema, wire = setup(monkeypatch)
    service.settings.apertus_context_chars = pack.request_characters(wire.system,
        pack.provider_input(wire, wire.references), pack.bounded_schema(wire.schema, wire.references), provider='swisscom') + 1
    calls, selections, finals = [], [], []
    actual_select = pack.select_evidence

    async def select(*args, **kwargs):
        selections.append(bool(kwargs.get('request_size')))
        return await actual_select(*args, **kwargs)

    async def complete(system, content, **options):
        payload = json.loads(content)
        calls.append((system, payload, options['response_schema']))
        assert options['budget'].max_requests == 1
        assert pack.request_characters(system, payload, options['response_schema'], provider='swisscom') <= service.settings.apertus_context_chars
        if len(calls) == 2:
            raise DomainError('Repair dispatch unavailable', 503, 'model_rate_limited')
        if len(calls) == 1 or malformed_resumed_repair and len(calls) == 3:
            return json.dumps(answer(wire, action='clarify'))
        refs = [p['citation_ref'] for source in payload.get('original_evidence', payload)['sources']
            for p in source['excerpts'] if 'citation_ref' in p]
        return json.dumps(answer(wire, {k: wire.references[k] for k in refs}))

    async def reading(*args):
        return None

    async def final(service, work, wire, parsed, seconds, *, checkpoints, on_progress, **kwargs):
        proof = {'exact_point': parsed.mission_checkpoint.answer.points[0].model_dump()}
        finals.append(True)
        if len(finals) == 1:
            checkpoints.setdefault('final_reviews', {})['clauses:retained'] = proof
            on_progress()
            raise DomainError('Final check interrupted', 503, 'model_rate_limited')
        assert checkpoints['final_reviews']['clauses:retained'] == proof
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered',
            'factual_review': {'status': 'checked', 'pending_checks': []}}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered'}

    monkeypatch.setattr(pack, 'select_evidence', select)
    monkeypatch.setattr(service.model_client, 'complete', complete)
    monkeypatch.setattr(research_answer_review, 'original_check', reading)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_final_coverage, 'reconcile', coverage)
    with pytest.raises(DomainError, match='Repair dispatch unavailable'):
        await gateway.complete(service, work, '', schema, 90)
    assert selections == [False, True]
    assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''
    assert work[KEY]['parts']['format_repair']['mode'] == 'repacked_error_only'
    current = json.loads(json.dumps(work))
    if malformed_resumed_repair:
        with pytest.raises(WireError):
            await gateway.complete(service, current, '', schema, 90)
        assert len(calls) == 3 and not finals, 'The resumed repair cannot buy a second repair in that step'
        assert current[KEY]['stage'] == 'draft'
        current = json.loads(json.dumps(current))
    with pytest.raises(DomainError, match='Final check interrupted'):
        await gateway.complete(service, current, '', schema, 90)
    assert selections == [False, True] and calls[2] == calls[1]
    before = len(calls)
    assert current[KEY]['stage'] == 'finalizing'
    parsed = schema.model_validate_json(await gateway.complete(service, json.loads(json.dumps(current)), '', schema, 90))
    assert len(calls) == before and selections == [False, True] and len(finals) == 2
    assert parsed.mission_checkpoint.answer.points
