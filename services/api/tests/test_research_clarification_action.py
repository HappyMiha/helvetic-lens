"""Clarification controls are validated before routing; semantic checks are separate."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import (
    research_answer_review,
    research_evidence_pack,
    research_final_coverage,
    research_final_review,
    research_gateway,
)
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import checked_delivery
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire, WireError, shape_errors
from helvetic_lens.research_synthesis_resume import KEY, DraftCheckpoint

TEXT = 'The register distinguishes permitted use from distribution obligations.'


def work_input():
    return {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Explain the register requirements.', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'sha256': 'b' * 64,
            'url': 'https://example.test/register',
            'excerpts': [{'passage': 'p1', 'text': TEXT}]}]}}


def response(action='clarify', count=2, *, legacy=False):
    result = {'answer': {'status': 'possible_answer', 'remaining_gaps': [],
        'points': [{'statement': TEXT, 'evidence': [{'citation_ref': 1, 'role': 'support'}]}]},
        'next_action': action, 'next_checks': [], 'deepen_branches': []}
    if action == 'clarify':
        result.update(clarification='Which activity should the investigation address?',
            directions=[{'question': question, 'why': 'The register distinguishes these obligations.',
                'citation_ref': 1} for question in
                ['Explain permitted use.', 'Explain distribution.', 'Compare both activities.'][:count]])
        if not legacy:
            result['next_action'] = {'kind': 'clarify', **{key: result.pop(key)
                for key in ('clarification', 'directions')}}
    return result


@pytest.mark.parametrize('invalid', ['missing', 'missing_question', 'blank_question', 'one_direction',
    'too_many', 'blank_direction', 'duplicate', 'uncited', 'foreign_reference'])
@pytest.mark.parametrize('legacy', [False, True])
def test_clarify_requires_a_real_cited_choice(invalid, legacy):
    wire = EvidenceWire(work_input(), mission_schema(Briefing), '')
    value = response(legacy=legacy)
    choice = value if legacy else value['next_action']
    if invalid == 'missing':
        choice.pop('clarification')
        choice.pop('directions')
    elif invalid == 'missing_question':
        choice.pop('clarification')
    elif invalid == 'blank_question':
        choice['clarification'] = ' \n\t '
    elif invalid == 'one_direction':
        choice['directions'].pop()
    elif invalid == 'too_many':
        choice['directions'] *= 2
    elif invalid == 'blank_direction':
        choice['directions'][0]['question'] = ' ' * 5
    elif invalid == 'duplicate':
        choice['directions'][1]['question'] = ' EXPLAIN   permitted use. '
    elif invalid == 'uncited':
        choice['directions'][1].pop('citation_ref')
    else:
        choice['directions'][1]['citation_ref'] = 999
    with pytest.raises(WireError) as error:
        wire.decode(json.dumps(value))
    assert any(item['path'][:1] == ['next_action'] for item in error.value.validation_errors)


@pytest.mark.parametrize('count', [2, 3])
@pytest.mark.parametrize('legacy', [False, True])
def test_valid_clarification_keeps_exact_citations_and_waits_for_choice(count, legacy):
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work_input(), schema, '')
    raw = response(count=count, legacy=legacy)
    raw['next_checks'] = [{'question': 'What does the register say about distribution?',
        'query': 'https://example.test/guide', 'purpose': 'Read the related original.',
        'kind': 'missing_evidence', 'priority': 1, 'catalogues': [], 'citation_ref': 1}]
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert all((direction.source_id, direction.locator, direction.quote) == ('a' * 36, 'p1', TEXT)
        for direction in parsed.directions)
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))) == parsed
    encoded = json.loads(wire.encode_checkpoint(parsed))
    assert encoded['next_action']['kind'] == 'clarify'
    assert not {'clarification', 'directions'} & encoded.keys()
    delivered = checked_delivery(parsed)
    assert delivered.mission_checkpoint.action == 'clarify'
    assert delivered.clarification == parsed.clarification and len(delivered.directions) == count
    assert not delivered.mission_checkpoint.next_checks, 'Incidental reading is not a chosen alternative'


@pytest.mark.parametrize('action', ['finish', 'continue'])
def test_normal_actions_keep_existing_optional_field_behavior(action):
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work_input(), schema, '')
    raw = {**response(action), 'clarification': 'Decorative prose is not a user choice.', 'directions': []}
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert parsed.mission_checkpoint.action == action and not parsed.clarification and not parsed.directions
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))) == parsed


def test_nonmission_briefing_keeps_empty_clarification_and_no_choice():
    wire = EvidenceWire(work_input(), Briefing, '')
    raw = {'understanding': 'The register supplies the applicable requirements.',
        'findings': [{'statement': TEXT, 'basis': 'direct', 'citation_ref': 1}],
        'uncertainties': ['The activity to examine remains unspecified.'], 'clarification': '', 'directions': []}
    parsed = Briefing.model_validate_json(wire.decode(json.dumps(raw)))
    assert not parsed.clarification and not parsed.directions


@pytest.mark.parametrize('invalid', ['finish_kind', 'unknown_kind', 'extra_field', 'mixed_flat_fields', 'bare_clarify'])
def test_typed_action_grammar_cannot_omit_or_contradict_its_choice(invalid):
    wire = EvidenceWire(work_input(), mission_schema(Briefing), '')
    raw = response()
    if invalid in {'finish_kind', 'unknown_kind'}:
        raw['next_action']['kind'] = 'finish' if invalid == 'finish_kind' else 'choose'
    elif invalid == 'extra_field':
        raw['next_action']['query'] = 'Unaccepted search instruction'
    elif invalid == 'mixed_flat_fields':
        raw.update(clarification='A different question', directions=[])
    else:
        raw['next_action'] = 'clarify'
    assert shape_errors(raw, wire.schema, wire.schema['$defs']), 'The provider grammar must reject this shape'
    with pytest.raises(WireError):
        wire.decode(json.dumps(raw))


def test_typed_clarification_uses_only_dispatched_citations():
    work = work_input()
    work['input']['sources'].append({'id': 'c' * 36, 'kind': 'public_source',
        'excerpts': [{'passage': 'other', 'text': 'A second register distinguishes the two activities.'}]})
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '')
    bounded = research_evidence_pack.bounded_schema(wire.schema, {2: wire.references[2]})
    raw = response()
    raw['answer']['points'][0]['evidence'][0]['citation_ref'] = 2
    raw['next_action']['directions'][0]['citation_ref'] = 2
    with pytest.raises(WireError) as caught:
        research_gateway.decode_provider_response(wire, json.dumps(raw), bounded)
    assert any(error['path'][:2] == ['next_action', 'directions'] for error in caught.value.validation_errors)
    raw['next_action']['directions'][1]['citation_ref'] = 2
    parsed = schema.model_validate_json(research_gateway.decode_provider_response(wire, json.dumps(raw), bounded))
    assert all(direction.source_id == 'c' * 36 and direction.quote == wire.references[2]['quote']
        for direction in parsed.directions)


def test_empty_selected_originals_disable_cited_clarification_only():
    wire = EvidenceWire(work_input(), mission_schema(Briefing), '')
    bounded = research_evidence_pack.bounded_schema(wire.schema, {})
    assert bounded['properties']['next_action']['anyOf'] == [{'type': 'string', 'enum': ['continue', 'finish']}]
    for action in ['continue', 'finish', response()['next_action']]:
        raw = response('finish')
        raw.update(next_action=action, answer={'status': 'not_found', 'points': [], 'remaining_gaps': []})
        if isinstance(action, dict):
            with pytest.raises(WireError):
                research_gateway.decode_provider_response(wire, json.dumps(raw), bounded)
        else:
            decoded = json.loads(research_gateway.decode_provider_response(wire, json.dumps(raw), bounded))
            assert decoded['mission_checkpoint']['action'] == action
    assert len(wire.schema['properties']['next_action']['anyOf']) == 2


def test_typed_clarification_roundtrips_legacy_request_sections():
    work = work_input()
    work['input']['original_question'] = 'Explain permitted use. Explain distribution.'
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    raw = response()
    point = raw['answer'].pop('points')[0]
    raw['answer']['responses'] = {key: {'disposition': 'answered', 'points': [deepcopy(point)], 'remaining_gap': ''}
        for key in wire.request_keys}
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert parsed.mission_checkpoint.action == 'clarify' and len(parsed.directions) == 2
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))) == parsed


def test_material_action_schema_invalidates_old_coherent_qualified_cache():
    work = work_input()
    original = deepcopy(work)
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    old_schema = deepcopy(wire.schema)
    old_action = old_schema['properties']['next_action']['anyOf'][1]
    old_schema['properties'].update({key: old_action['properties'][key] for key in ('clarification', 'directions')})
    old_schema['properties']['next_action'] = {'type': 'string', 'enum': ['continue', 'clarify', 'finish']}
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    args = [settings, wire.system, 'unchanged-workflow']
    old = DraftCheckpoint(work, *args, old_schema, json.dumps(wire.input), {})
    old.parts['deferred_final_review'] = {'status': 'qualified_delivery'}
    old.save('finalizing', json.dumps(response('finish')), [], {})
    restored = DraftCheckpoint(work, *args, wire.schema, json.dumps(wire.input), {})
    assert restored.value is None and not restored.parts and KEY not in work
    assert work['input'] == original['input'], 'Contract changes do not erase retained source reading'


def gateway_fixture(monkeypatch, replies, *, interrupt_final=False):
    work, events = work_input(), []
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    schema = mission_schema(Briefing)
    original_check = research_answer_review.original_check

    async def select(service, wire, question, seconds, **kwargs):
        return deepcopy(wire.references)

    async def complete(system, content, **kwargs):
        events.append('model')
        assert kwargs['budget'].max_requests == 1
        assert kwargs['max_output_tokens'] == max(4096, settings.apertus_max_tokens)
        return json.dumps(replies.pop(0))

    async def reading(settings, supplied, wire, checkpoint, seconds, **kwargs):
        if kwargs:
            return await original_check(settings, supplied, wire, checkpoint, seconds, **kwargs)
        events.append('reading:' + checkpoint.action)

    class Choice:
        async def choose(self, state, instructions, criteria):
            events.append('reading:clarify')
            return Decision('jev', 'test', 'user_choice', {'user_choice': 1}, 1, 1, 1, 1, 1)

    async def final(service, supplied, wire, parsed, seconds, **kwargs):
        events.append('final')
        if interrupt_final and events.count('final') == 1:
            raise DomainError('Review unavailable', 503, 'model_rate_limited')
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered',
            'factual_review': {'status': 'checked', 'pending_checks': []}}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered'}

    monkeypatch.setattr(research_evidence_pack, 'select_evidence', select)
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(research_answer_review, 'original_check', reading)
    monkeypatch.setattr(research_answer_review.decision, 'engines', lambda settings: {'jev': Choice()})
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_final_coverage, 'reconcile', coverage)
    return SimpleNamespace(settings=settings, model_client=model), work, schema, events


@pytest.mark.asyncio
@pytest.mark.parametrize('repaired_action', ['clarify', 'continue', 'finish'])
async def test_gateway_repairs_bad_action_before_reading_or_factual_review(monkeypatch, repaired_action):
    malformed = response()
    malformed['next_action'].pop('clarification')
    malformed['next_action'].pop('directions')
    service, work, schema, events = gateway_fixture(monkeypatch, [malformed, response(repaired_action)])
    parsed = schema.model_validate_json(await research_gateway.complete(service, work, '', schema, 90))
    assert events == ['model', 'model', 'reading:' + repaired_action, 'final']
    assert work['model_route']['format_repair'] is True
    assert parsed.mission_checkpoint.action == repaired_action
    assert parsed.mission_checkpoint.answer.points[0].evidence[0].quote == TEXT


@pytest.mark.asyncio
async def test_failed_repair_stays_private_and_invalid_draft_is_revalidated_on_resume(monkeypatch):
    malformed = response()
    malformed['next_action'].pop('clarification')
    malformed['next_action'].pop('directions')
    service, work, schema, events = gateway_fixture(monkeypatch, [malformed, malformed, response('finish')])
    with pytest.raises(WireError):
        await research_gateway.complete(service, work, '', schema, 90)
    assert events == ['model', 'model']
    assert work[KEY]['stage'] == 'draft' and 'completed_answer_delivery' not in work
    resumed = json.loads(json.dumps(work))
    parsed = schema.model_validate_json(await research_gateway.complete(service, resumed, '', schema, 90))
    assert events == ['model', 'model', 'model', 'reading:finish', 'final']
    assert resumed['model_route']['resumed_stage'] == 'draft'
    assert parsed.mission_checkpoint.action == 'finish'


@pytest.mark.asyncio
async def test_valid_clarification_resumes_without_new_draft_or_losing_alternatives(monkeypatch):
    service, work, schema, events = gateway_fixture(monkeypatch, [response()], interrupt_final=True)
    with pytest.raises(DomainError, match='Review unavailable'):
        await research_gateway.complete(service, work, '', schema, 90)
    assert work[KEY]['stage'] == 'finalizing'
    restored = json.loads(json.dumps(work))
    parsed = schema.model_validate_json(await research_gateway.complete(service, restored, '', schema, 90))
    assert events == ['model', 'reading:clarify', 'final', 'final']
    assert restored['model_route']['resumed_stage'] == 'finalizing'
    assert parsed.mission_checkpoint.action == 'clarify' and len(parsed.directions) == 2
