"""Action arbitration mechanics; scripted choices do not establish source truth."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_clarification_action import response, work_input

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_evidence_pack as pack
from helvetic_lens import research_final_coverage, research_final_review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import KEY


def context():
    work = work_input()
    source = work['input']['sources'][0]
    source['discovery_links'] = [{'url': 'https://example.test/original', 'kind': 'document',
        'title': 'Original register', 'context': source['excerpts'][0]['text']}]
    work['input']['research_mission']['discovery_frontiers'] = [{'branch_id': 'retained-frontier',
        'query': 'original register', 'remaining_candidates': 1,
        'unread_candidates': [{'title': 'Original register', 'url': 'https://example.test/original'}]}]
    work['mission_continuation'] = {'frontiers': ['retained-frontier'], 'unfinished': False,
        'signature': 'current', 'previous_signature': 'earlier', 'next_slots': 4,
        'questions': [], 'queries': [], 'published_question_ids': []}
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '')
    raw = response()
    raw['next_action']['clarification'] = 'Can you locate and read the original register?'
    raw['next_checks'] = [{'question': 'Read the original register.', 'query': 'https://example.test/original',
        'purpose': 'Resolve the original requested requirements.', 'priority': 1, 'catalogues': [],
        'kind': 'independent_verification', 'citation_ref': 1}]
    return work, schema, wire, schema.model_validate_json(wire.decode(json.dumps(raw)))


def engines(monkeypatch, choices):
    calls = []

    class Engine:
        async def choose(self, state, instructions, criteria):
            calls.append(deepcopy(state))
            assert 'user_choice' in criteria and 'none' in criteria
            assert 'only the user can supply' in instructions
            choice = choices.pop(0)
            if choice == 'unavailable':
                raise DecisionUnavailable('not_configured')
            return Decision('jev', 'test', choice, {choice: 1}, 1, 1, 1, 1, 1)

    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine()})
    return calls


async def decide(work, wire, parsed, *, previous=None, seconds=60):
    return await review.original_check(Settings(_env_file=None, apertus_provider='swisscom'), work, wire,
        parsed.mission_checkpoint, seconds, clarification=parsed.clarification,
        directions=parsed.directions, previous=previous)


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', ['user_choice', 'none', 'check:0', 'frontier:0', '0'])
async def test_clarification_is_an_explicit_action_decision_and_exact_result_resumes(monkeypatch, choice):
    work, schema, wire, parsed = context()
    before = parsed.model_dump()
    calls = engines(monkeypatch, [choice])
    receipt = await decide(work, wire, parsed)
    assert calls[0]['proposed_clarification']['question'] == before['clarification']
    assert calls[0]['proposed_clarification']['directions'] == before['directions']
    assert calls[0]['proposed_frontiers']['frontier:0']['unread_candidates']
    assert receipt['contract'] == review.CLARIFICATION_READING
    checkpoint = parsed.mission_checkpoint
    assert checkpoint.answer.model_dump()['points'] == before['mission_checkpoint']['answer']['points']
    assert checkpoint.action == ('clarify' if choice == 'user_choice' else 'finish' if choice == 'none' else 'continue')
    if choice != 'user_choice':
        parsed.clarification, parsed.directions = '', []
    if choice == 'frontier:0':
        assert checkpoint.deepen_branches == ['retained-frontier'] and not checkpoint.next_checks
    restored = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed)))
    assert await decide(work, wire, restored, previous=json.loads(json.dumps(receipt))) == receipt
    assert len(calls) == 1, 'A performed exact action decision is not purchased again'


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['question', 'answer', 'controls', 'frontier', 'policy', 'source'])
async def test_arbitration_reuse_requires_current_input_policy_and_control_ownership(monkeypatch, change):
    work, schema, wire, parsed = context()
    calls = engines(monkeypatch, ['user_choice', 'user_choice'])
    receipt = await decide(work, wire, parsed)
    if change == 'question':
        work['input']['original_question'] = 'Explain registration eligibility.'
    elif change == 'answer':
        parsed.mission_checkpoint.answer.points[0].statement = 'A corrected interpretation remains subject to review.'
    elif change == 'controls':
        parsed.clarification = 'Which jurisdiction governs your intended use?'
        parsed.directions[0].question = 'Examine the first jurisdiction.'
    elif change == 'frontier':
        wire.input['research_mission']['discovery_frontiers'] = []
    elif change == 'policy':
        monkeypatch.setattr(review, 'CLARIFICATION_READING_INSTRUCTIONS', review.CLARIFICATION_READING_INSTRUCTIONS + ' Updated action scope.')
    else:
        wire.references = {}
        with pytest.raises(DomainError) as caught:
            await decide(work, wire, parsed, previous=receipt)
        assert caught.value.code == 'invalid_evidence' and len(calls) == 1
        return
    changed = parsed.model_dump()
    revised = await decide(work, wire, parsed, previous=receipt)
    assert len(calls) == 2
    assert revised['policy_fingerprint'] != receipt['policy_fingerprint'] if change == 'policy' else revised['input_fingerprint'] != receipt['input_fingerprint']
    if change == 'controls':
        assert calls[-1]['proposed_clarification']['question'] == changed['clarification']
        assert revised['proposal']['directions'] == changed['directions'], 'Never restore old user intent'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['unavailable', 'unknown', 'deadline', 'frontier'])
async def test_unavailable_or_ineligible_clarification_never_silently_approves_or_finishes(monkeypatch, failure):
    work, schema, wire, parsed = context()
    calls = engines(monkeypatch, ['unavailable' if failure == 'unavailable' else 'unknown'])
    if failure == 'frontier':
        parsed.mission_checkpoint.deepen_branches = ['not-supplied']
    before = parsed.model_dump()
    with pytest.raises(DomainError) as caught:
        await decide(work, wire, parsed, seconds=0 if failure == 'deadline' else 60)
    assert caught.value.code == ('invalid_evidence' if failure == 'frontier' else 'model_temporarily_unavailable')
    assert parsed.model_dump() == before
    assert len(calls) == (1 if failure in {'unavailable', 'unknown'} else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['local', 'private', 'mixed', 'empty'])
async def test_out_of_scope_does_not_gain_hosted_arbitration_or_approval(monkeypatch, scope):
    work, schema, wire, parsed = context()
    calls = engines(monkeypatch, [])
    if scope == 'private':
        work['input']['sources'][0]['kind'] = 'uploaded_file'
    elif scope == 'mixed':
        work['input']['sources'].append({'kind': 'uploaded_file'})
    elif scope == 'empty':
        work['input']['sources'] = []
    assert await review.original_check(Settings(_env_file=None, apertus_provider='docker' if scope == 'local' else 'swisscom'), work, wire,
        parsed.mission_checkpoint, 60, clarification=parsed.clarification, directions=parsed.directions) is None
    assert not calls and parsed.mission_checkpoint.action == 'clarify'


@pytest.mark.asyncio
async def test_private_document_clarification_keeps_legacy_completion_without_new_decision(monkeypatch):
    work, schema, wire, initial = context()
    work['input']['sources'][0]['kind'] = 'uploaded_file'
    calls = engines(monkeypatch, [])
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'),
        model_client=ModelClient(Settings(_env_file=None, apertus_provider='swisscom')))

    async def select(service, wire, *args, **kwargs):
        return deepcopy(wire.references)

    async def complete(*args, **kwargs):
        return wire.encode_checkpoint(initial)

    async def final(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered',
            'factual_review': {'status': 'checked', 'pending_checks': []}}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered'}

    monkeypatch.setattr(pack, 'select_evidence', select)
    monkeypatch.setattr(service.model_client, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_final_coverage, 'reconcile', coverage)
    parsed = schema.model_validate_json(await gateway.complete(service, work, '', schema, 90))
    assert parsed.mission_checkpoint.action == 'clarify' and parsed.clarification == initial.clarification
    assert not calls and work['model_route']['answer_review']['original_reading'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', ['user_choice', 'none', 'frontier:0'])
async def test_finalizing_missing_action_receipt_keeps_draft_proofs_and_resumes_exact_decision(monkeypatch, choice):
    work, schema, wire, initial = context()
    decisions = ['user_choice', 'unavailable', choice]
    calls = engines(monkeypatch, decisions)
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    service = SimpleNamespace(settings=settings, model_client=ModelClient(settings))
    writers, finals = [], []
    proofs = {f'clauses:checked-{i}': {'exact_point': initial.mission_checkpoint.answer.points[0].model_dump()}
        for i in range(6)}

    async def select(service, wire, *args, **kwargs):
        return deepcopy(wire.references)

    async def complete(*args, **kwargs):
        writers.append(True)
        return wire.encode_checkpoint(initial)

    async def final(service, supplied, wire, parsed, seconds, *, checkpoints, on_progress, **kwargs):
        finals.append(True)
        if len(finals) == 1:
            checkpoints['final_reviews'] = deepcopy(proofs)
        assert checkpoints['final_reviews'] == proofs
        on_progress()
        if len(finals) < 3:
            raise DomainError('Retained factual work', 503, 'model_rate_limited')
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered',
            'factual_review': {'status': 'checked', 'pending_checks': []}}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered'}

    monkeypatch.setattr(pack, 'select_evidence', select)
    monkeypatch.setattr(service.model_client, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_final_coverage, 'reconcile', coverage)
    with pytest.raises(DomainError, match='Retained factual work'):
        await gateway.complete(service, work, '', schema, 90)
    # Exact existing finalizing state, predating semantic action arbitration.
    saved = work[KEY]
    saved['review'].pop('original_reading')
    saved['fingerprint'] = fingerprint({key: value for key, value in saved.items() if key != 'fingerprint'})
    before = deepcopy(saved)
    with pytest.raises(DomainError, match='next-reading decision'):
        await gateway.complete(service, work, '', schema, 90)
    assert work[KEY]['stage'] == 'finalizing' and work[KEY]['raw'] == before['raw']
    assert work[KEY]['parts'] == before['parts'] and len(writers) == 1 and len(finals) == 1
    if choice == 'frontier:0':
        parsed = schema.model_validate_json(await gateway.complete(service, work, '', schema, 90))
        assert work['private_continuation'] and parsed.mission_checkpoint.deepen_branches == ['retained-frontier']
        assert parsed.mission_checkpoint.action == 'continue' and not parsed.clarification and not parsed.directions
        assert len(finals) == 1 and work[KEY]['parts']['final_reviews'] == proofs
    else:
        with pytest.raises(DomainError, match='Retained factual work'):
            await gateway.complete(service, work, '', schema, 90)
        assert work[KEY]['stage'] == 'finalizing' and work[KEY]['parts']['final_reviews'] == proofs
        restored = json.loads(json.dumps(work))
        parsed = schema.model_validate_json(await gateway.complete(service, restored, '', schema, 90))
        assert parsed.mission_checkpoint.action == ('clarify' if choice == 'user_choice' else 'finish')
        assert bool(parsed.clarification) == (choice == 'user_choice')
        assert len(finals) == 3
    assert len(writers) == 1 and len(calls) == 3
