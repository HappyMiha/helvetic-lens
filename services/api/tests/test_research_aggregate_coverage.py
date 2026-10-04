"""A shared answer covers its complete question, not host-invented sentence tasks."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_coverage as coverage
from helvetic_lens import research_final_review as final
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import AssessedBriefing, AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire, explicit_requests


def fixture():
    question = ('I operate a private archive. Must I publish its records? Which notices are required? '
        'Use the official archive rules. Use https://example.test/rules.')
    text = 'The archive need not publish its private records.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {'original_question': question,
        'research_mission': {}, 'sources': [{'id': 'archive', 'kind': 'public_source',
            'url': 'https://example.test/rules', 'title': 'Archive rules', 'sha256': 'a' * 64,
            'excerpts': [{'passage': 'p1', 'text': text}]}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': text,
        'evidence': [{**wire.references[1], 'role': 'support'}]}], limitations=[])
    return work, wire, answer


@pytest.mark.parametrize('shared', [False, True])
def test_writer_preserves_complete_question_and_source_instructions_with_legacy_slot_compatibility(shared):
    work, _, _ = fixture()
    before = deepcopy(work)
    wire = EvidenceWire(work, mission_schema(Briefing), '', shared_answer=shared)
    question = work['input']['original_question']
    assert wire.input['original_question'] == question
    assert wire.input['source_instructions'] == ['Use https://example.test/rules.']
    assert wire.input['requests_to_address'] == ([question] if shared else explicit_requests(question))
    assert bool(wire.request_keys) is (not shared) and work == before
    assert coverage.coverage_requests(work, wire) == ([question] if shared else list(wire.request_keys.values()))


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', ['covered', 'missing', 'unavailable'])
async def test_aggregate_missing_is_not_a_specific_knowledge_gap_and_exact_receipt_is_shared(monkeypatch, choice):
    work, wire, answer = fixture()
    model_gap = 'The notice for an unusual transfer remains unspecified in the supplied rules.'
    old_host = 'This answer has not resolved the requested part: Must I publish its records?'
    unowned_notice = 'This answer has not resolved the requested part: Which notices are required?'
    answer.limitations = [model_gap, old_host, unowned_notice]
    wire.workflow_gaps = {old_host}
    calls, cache = [], {}

    class Engine:
        async def choose(self, state, instructions, criteria):
            calls.append(deepcopy(state))
            assert state['specific_request'] == work['input']['original_question']
            assert state['answer_points'] == {'P0': answer.points[0].statement}
            if choice == 'unavailable':
                raise DecisionUnavailable('timeout')
            return Decision('jev', 'scripted', choice, {}, 1, 1, 0, 1, 1)

    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine()})
    result = await audit.audit(Settings(_env_file=None), work, wire, answer, 60,
        coverage_only=True, checkpoints=cache)
    assert result['question_coverage'] == (None if choice == 'unavailable' else choice)
    assert [hint['user_request'] for hint in result['hints']] == (
        [work['input']['original_question']] if choice == 'missing' else [])
    reconciled = await coverage.reconcile(Settings(_env_file=None), work, wire, answer, 60, checkpoints=cache)
    assert reconciled['question_coverage'] == result['question_coverage']
    assert answer.limitations == [model_gap, unowned_notice], 'Only exact host-owned historical notices are retired'
    assert len(calls) == (2 if choice == 'unavailable' else 1)
    assert reconciled['status'] == ('partial' if choice == 'unavailable' else 'checked')
    assert answer.status == 'partial', 'A genuine reviewed gap is not erased by an aggregate covered label'


@pytest.mark.asyncio
async def test_legacy_slot_coverage_still_resolves_its_owned_notice(monkeypatch):
    work, wire, answer = fixture()
    request = 'Must I publish its records?'
    notice = 'A cited answer could not be validated for: ' + request
    wire.request_keys = {'R0': request}
    wire.response_slots = {'R0': {'disposition': 'unresolved', 'remaining_gap': notice}}
    wire.workflow_gaps = {notice}
    answer.limitations = [notice]
    calls = []

    class Engine:
        async def choose(self, state, instructions, criteria):
            calls.append(state)
            return Decision('jev', 'scripted', 'covered', {}, 1, 1, 0, 1, 1)

    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine()})
    result = await coverage.reconcile(Settings(_env_file=None), work, wire, answer, 60)
    assert [state['specific_request'] for state in calls] == [request]
    assert result['removed_notices'] == 1 and not answer.limitations


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', ['covered', 'missing'])
async def test_gateway_projects_aggregate_partial_without_inventing_fragment_limitations(monkeypatch, choice):
    work, _, answer = fixture()
    work['input']['assessment_question'] = {'question_id': 'current-question'}
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    calls = []

    class Engine:
        async def choose(self, state, instructions, criteria):
            assert state['specific_request'] == work['input']['original_question']
            calls.append(state)
            return Decision('jev', 'scripted', choice, {}, 1, 1, 0, 1, 1)

    async def complete(*args, **kwargs):
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [{'statement': answer.points[0].statement, 'evidence': [{'citation_ref': 1, 'role': 'support'}]}]},
            'next_action': 'finish'})

    async def no_original(*args, **kwargs):
        return None

    async def finalized(service, work, wire, parsed, seconds, **kwargs):
        result = await audit.audit(service.settings, work, wire, parsed.mission_checkpoint.answer, seconds,
            coverage_only=True, checkpoints=kwargs['checkpoints'])
        result['factual_review'] = {'status': 'checked', 'pending_checks': []}
        return result

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(audit, 'original_check', no_original)
    monkeypatch.setattr(final, 'finalize', finalized)
    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine()})
    schema = mission_schema(AssessedBriefing)
    delivered = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    actual = delivered.mission_checkpoint.answer
    assert actual.points[0].statement == answer.points[0].statement and not actual.limitations
    assert actual.status == ('partial' if choice == 'missing' else 'possible_answer')
    assert delivered.uncertainties == [] and delivered.assessment.status == actual.status
    assert len(calls) == 1, 'Final reconciliation reuses coverage of the same retained answer'
    if choice == 'missing':
        assert delivered.mission_checkpoint.reason == (
            'The cited findings are retained; coverage of the complete request has not been established.')
    assert 'deferred_review_verification' not in work


@pytest.mark.asyncio
async def test_aggregate_missing_uses_existing_amendment_once_and_preserves_checked_sibling(monkeypatch):
    from test_research_review_resilience import fixture as final_fixture
    from test_research_review_resilience import response

    from helvetic_lens.product_exploration import AssessmentPoint

    texts, work, wire, parsed = final_fixture()
    answer = parsed.mission_checkpoint.answer
    answer.points, answer.limitations = answer.points[:1], []
    original = answer.points[0].model_dump()
    amendments, checks, choices = [], [], []

    class Engine:
        async def choose(self, state, instructions, criteria):
            assert state['specific_request'] == work['input']['original_question']
            choices.append(list(state['answer_points'].values()))
            choice = 'missing' if len(state['answer_points']) == 1 else 'covered'
            return Decision('jev', 'scripted', choice, {}, 1, 1, 0, 1, 1)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            checks.append(next(iter(payload['final_claims_and_gaps'].values()))['statement'])
            return response(payload)

    async def advisory(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def amend(service, current_wire, request, seconds, **kwargs):
        amendments.append(request)
        assert request == work['input']['original_question']
        assert kwargs['amendments'] == {'P0': original} and kwargs['allow_append']
        assert kwargs['correction'] is None
        return [AssessmentPoint(statement=texts[1], evidence=[{**wire.references[2], 'role': 'support'}])], '', {
            'status': 'proposed', 'replace_point': 'new'}

    monkeypatch.setattr(coverage.decision, 'engines', lambda settings: {'jev': Engine()})
    monkeypatch.setattr(audit, 'audit_points', advisory)
    monkeypatch.setattr(final, 'answer_request', amend)
    result = await final.finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        work, wire, parsed, 90, checkpoints={}, defer_pending=True)
    assert amendments == [work['input']['original_question']]
    assert answer.points[0].model_dump() == original and checks == texts[:2]
    assert result['question_coverage'] == 'covered' and result['hints'] == []
    assert choices == [[texts[0]], texts[:2]], 'Coverage is rebound after the actual answer changes'
