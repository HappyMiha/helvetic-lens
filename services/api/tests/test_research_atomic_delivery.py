"""A dossier preserves independently grounded conclusions through final delivery."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_answer_parts import fixture, selection_json

from helvetic_lens import research_answer_parts as parts
from helvetic_lens import research_answer_review as review
from helvetic_lens import research_final_coverage as coverage
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_direction_assessment import DirectionAssessment
from helvetic_lens.product_exploration import AssessmentOutcome, AssessmentPoint, QuestionAssessment
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.research_model_transport import WireError


@pytest.mark.asyncio
async def test_atomic_pack_resumes_later_point_without_losing_siblings_or_rebuying_draft():
    wire, _, _ = fixture(2)
    state, calls = {}, []
    blocked = [False]
    def point(year):
        return {'statement': f'The record was published in {year}.',
            'evidence': [{'citation_ref': 1, 'role': 'support'}]}
    class Model:
        async def complete(self, system, text, **options):
            assert options['max_output_tokens'] <= 8192
            if 'citation_refs' in options['response_schema']['properties']:
                calls.append('select')
                return selection_json([1], options)
            if 'points' in options['response_schema']['properties']:
                calls.append('draft')
                return json.dumps({'points': [point(2001), point(2098), point(2099)], 'remaining_gap': ''})
            previous = json.loads(text)['previous_proposal']
            calls.append(previous['statement'])
            if '2098' in previous['statement']:
                return json.dumps(previous)  # This one remains unsupported.
            if not blocked[0]:
                blocked[0] = True
                raise DomainError('Interrupted during the last point', 503, 'model_upstream_timeout')
            return json.dumps({**point(1999), 'remaining_gap': '',
                'evidence': [{'citation_ref': 2, 'role': 'support'}]})
    service = SimpleNamespace(model_client=Model())
    with pytest.raises(DomainError):
        await parts.answer_request(service, wire, 'Compare the editions.', 60, checkpoints=state, max_points=8)
    result, gap, receipt = await parts.answer_request(service, wire, 'Compare the editions.', 60,
        checkpoints=json.loads(json.dumps(state)), max_points=8)
    assert [p.statement for p in result] == [point(2001)['statement'], point(1999)['statement']]
    assert [p.evidence[0].quote for p in result] == [wire.references[i]['quote'] for i in (1, 2)]
    assert receipt['workflow_gap'] and gap.startswith('A cited answer could not be validated for: ')
    assert calls == ['select', 'draft', point(2098)['statement'], point(2099)['statement'], point(2099)['statement']]


def test_multi_point_slot_capacity_round_trips_and_excess_is_rejected():
    wire, parsed, schema = fixture(3)
    raw = json.loads(wire.encode_checkpoint(parsed))
    assert [parts.request_capacity(wire, key) for key in wire.request_keys] == [3, 3, 2]
    for key, capacity in zip(wire.request_keys, (3, 3, 2)):
        raw['answer']['responses'][key]['points'] *= capacity
    decoded = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert len(decoded.mission_checkpoint.answer.points) == 8
    assert wire.point_requests == ['r1'] * 3 + ['r2'] * 3 + ['r3'] * 2
    assert json.loads(wire.encode_checkpoint(decoded))['answer']['responses'] == raw['answer']['responses']
    raw['answer']['responses']['r3']['points'].append(raw['answer']['responses']['r3']['points'][0])
    with pytest.raises((ValueError, WireError)):
        wire.decode(json.dumps(raw))


@pytest.mark.asyncio
@pytest.mark.parametrize('gap_only', [False, True])
async def test_correction_retains_good_owned_siblings_and_checks_each_replacement(monkeypatch, gap_only):
    def point(name):
        return AssessmentPoint(statement=f'{name} operates the registry.', evidence=[{
            'source_id': 'a' * 36, 'locator': name, 'quote': f'{name} operates the registry.', 'role': 'support'}])
    good, sibling, bad = point('Good'), point('Sibling'), point('Wrong')
    answer = AssessmentOutcome(status='partial', points=[good, sibling] if gap_only else [good, bad, sibling],
        limitations=['The operator is unknown.'] if gap_only else [])
    wire = SimpleNamespace(input={'original_question': 'Who operates the registries?'}, references={},
        request_keys={'r1': 'First registries?', 'r2': 'Second registry?'},
        point_requests=['r1', 'r2'] if gap_only else ['r1', 'r1', 'r2'],
        response_slots={'r1': {'disposition': 'unresolved' if gap_only else 'answered',
            'remaining_gap': answer.limitations[0] if gap_only else ''},
            'r2': {'disposition': 'answered', 'remaining_gap': ''}})
    cache, calls = {}, []
    blocked = [False]
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': []}
    async def reasoned(*args, **kwargs):
        if any(p.statement.startswith('New') for p in answer.points):
            if not blocked[0]:
                blocked[0] = True
                raise DomainError('Interrupted after replacement', 503, 'model_upstream_timeout')
            return {'status': 'checked', 'hints': [], 'pending_checks': []}
        return {'status': 'checked', 'hints': [{'path': ['answer', 'limitations', 0] if gap_only else ['answer', 'points', 1],
            'review_signal': 'not_established', 'instruction': 'Use the original operators.'}], 'pending_checks': []}
    async def correct(*args, **kwargs):
        calls.append(kwargs)
        return [point('New North'), point('New South')], '', {'status': 'proposed'}
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(final, 'reasoned_review', reasoned)
    monkeypatch.setattr(final, 'answer_request', correct)
    args = (SimpleNamespace(settings=Settings(_env_file=None)), {'input': wire.input}, wire,
        SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer)), 60)
    with pytest.raises(DomainError):
        await final.finalize(*args, checkpoints=cache, on_progress=lambda: None, defer_pending=True)
    assert cache['final_correction_round']['completed'] == 1
    await final.finalize(*args, checkpoints=json.loads(json.dumps(cache)), on_progress=lambda: None, defer_pending=True)
    assert len(calls) == 1 and calls[0]['max_points'] == 3
    assert calls[0]['feedback']['already_answered'] == [good.model_dump()]
    assert good in answer.points and sibling in answer.points and len(answer.points) == 4
    assert wire.point_requests[answer.points.index(sibling)] == 'r2'
    assert not answer.limitations
    if not gap_only:
        for replacement in (p for p in answer.points if p.statement.startswith('New')):
            binding = fingerprint({'request_key': 'r1', 'point': replacement.model_dump()})
            assert cache['repair_concerns'][binding]['previous_statements'] == [bad.statement]


def coverage_fixture():
    wire, parsed, _ = fixture(2)
    answer = parsed.mission_checkpoint.answer
    answer.points = answer.points[:1]
    answer.points[0].statement = 'The first and second records were published in 2001.'
    wire.point_requests = ['r1']
    notice = 'A cited answer could not be validated for: ' + wire.request_keys['r2']
    wire.response_slots['r2'].update(disposition='unresolved', remaining_gap=notice)
    wire.workflow_gaps = {notice}
    answer.limitations = [notice, 'The exact publication day remains unknown.']
    answer.status = 'partial'
    return wire, parsed, notice


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', ['fully_answered', 'unresolved', 'unavailable'])
async def test_cross_slot_coverage_clears_only_verified_host_notice_and_preserves_projections(monkeypatch, choice):
    wire, parsed, notice = coverage_fixture()
    answer = parsed.mission_checkpoint.answer
    original = answer.model_dump()
    settings, cache, calls = Settings(_env_file=None), {}, []
    class Engine:
        async def choose(self, payload, system, criteria):
            calls.append(deepcopy(payload))
            assert payload['answer_points'] == {'P0': answer.points[0].statement}
            assert payload['specific_request'] == wire.request_keys['r2']
            if choice == 'unavailable':
                raise DecisionUnavailable('timeout')
            return Decision('jev', 'fixture', choice, {choice: 1}, 1, 1, 1, None, None)
    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    work = {'input': wire.input}
    result = await coverage.reconcile(settings, work, wire, answer, 60, checkpoints=cache)
    assert (notice not in answer.limitations) == (choice == 'fully_answered')
    assert 'The exact publication day remains unknown.' in answer.limitations
    assert wire.response_slots['r2']['remaining_gap'] == notice, 'Private drafting slots retain valid provenance'
    if choice != 'unavailable':
        answer = AssessmentOutcome.model_validate(original)
        await coverage.reconcile(settings, work, wire, answer, 60, checkpoints=json.loads(json.dumps(cache)))
        assert len(calls) == 1, 'Exact retained coverage does not buy another decision'
    assert result['removed_notices'] == (1 if choice == 'fully_answered' else 0)
    delivered = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason='Old gaps'),
        uncertainties=list(original['limitations']),
        assessment=QuestionAssessment(**original, question_id='q1'),
        direction_assessment=DirectionAssessment(**original, selection=None))
    coverage.synchronize_projections(delivered)
    assert delivered.uncertainties == answer.limitations
    assert delivered.assessment.model_dump(exclude={'question_id'}) == answer.model_dump()
    assert delivered.direction_assessment.model_dump(exclude={'selection'}) == answer.model_dump()
    assert delivered.assessment.question_id == 'q1'


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', ['private', 'model_gap', 'deadline'])
async def test_coverage_never_sends_private_data_or_clears_unverified_gaps(monkeypatch, blocked):
    wire, parsed, notice = coverage_fixture()
    if blocked == 'private':
        wire.input['sources'][0]['kind'] = 'private_file'
    if blocked == 'model_gap':
        wire.workflow_gaps = set()
    class Engine:
        async def choose(self, *args):
            pytest.fail('No authorized decision is possible')
    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    await coverage.reconcile(Settings(_env_file=None), {'input': wire.input}, wire, parsed.mission_checkpoint.answer,
        0 if blocked == 'deadline' else 60)
    assert notice in parsed.mission_checkpoint.answer.limitations


@pytest.mark.asyncio
async def test_positive_witness_roles_remove_false_conflict_without_changing_claims(monkeypatch):
    wire, parsed, schema = fixture(2)
    answer = parsed.mission_checkpoint.answer
    answer.points[0].evidence = [answer.points[0].evidence[0].model_copy(update={'role': 'counterevidence'})]
    answer.status = 'conflicting'
    original = answer.points[0].statement
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    async def reasoned(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'pending_checks': [],
            'positive_witnesses': {fingerprint(answer.points[0].model_dump()): [1]}}
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(final, 'reasoned_review', reasoned)
    await final.finalize(SimpleNamespace(settings=Settings(_env_file=None)), {'input': wire.input}, wire, parsed, 60)
    assert answer.status == 'possible_answer' and answer.points[0].statement == original
    assert answer.points[0].evidence[0].role == 'support'
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))).mission_checkpoint.answer == answer


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['unresolved_concern', 'nongap', 'step_deadline', 'invalid_response'])
async def test_inconclusive_completed_correction_does_not_block_valid_siblings(monkeypatch, reason):
    wire, parsed, schema = fixture(2)
    answer = parsed.mission_checkpoint.answer
    sibling = answer.points[0].model_copy(deep=True)
    if reason == 'nongap':
        parts.update_gap(wire, answer, 'r2', 'The registry exists.')
    pending_reason = 'unresolved_concern' if reason == 'nongap' else reason
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    async def reasoned(*args, **kwargs):
        return {'status': 'partial', 'points_checked': 1,
            'pending_checks': [{'item': 'P1', 'reason': pending_reason}],
            'hints': [{'path': ['answer', 'points', 1], 'review_signal': 'review_unavailable',
                'instruction': 'The previous objection has not been resolved.'}] +
                ([{'path': ['answer', 'limitations', 0], 'review_signal': 'not_a_gap', 'instruction': 'This is known.'}]
                    if reason == 'nongap' else [])}
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(final, 'reasoned_review', reasoned)
    state = {'final_correction_round': {'tasks': [], 'completed': 0, 'receipts': [], 'observations': []}}
    result = await final.finalize(SimpleNamespace(settings=Settings(_env_file=None)), {'input': wire.input},
        wire, parsed, 60, checkpoints=state, on_progress=lambda: None, defer_pending=True)
    if pending_reason == 'unresolved_concern':
        assert answer.points == [sibling] and wire.point_requests == ['r1']
        assert answer.status == 'partial' and len(answer.limitations) == 1
        assert result['factual_review']['pending_checks'] == []
        assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': pending_reason}]
        assert wire.request_keys['r2'] in answer.limitations[0]
        assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))).mission_checkpoint.answer == answer
    else:
        assert len(answer.points) == 2 and result['factual_review']['pending_checks']
