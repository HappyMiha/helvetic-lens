"""Final review searches its literal assertion without inventing a user request."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_evidence_pack as packing
from helvetic_lens.product_exploration import AssessmentEvidence, AssessmentOutcome, AssessmentPoint
from helvetic_lens.research_final_review import reasoned_review


def originals():
    texts = ['The permit ends when the specified triggering event occurs.',
        'A retained earlier objection concerns the original exception.',
        'The exception applies only to the stated class of equipment.',
        'An unrelated administrative fact remains in the original.']
    references = {key: {'source_id': f's{key}', 'locator': 'p1', 'quote': text}
        for key, text in enumerate(texts, 1)}
    return SimpleNamespace(input={'original_question': 'Explain the permit and its limitations.',
        'sources': [{'id': f's{key}', 'sha256': str(key) * 64, 'title': f'Original {key}',
            'url': f'https://example.test/{key}', 'excerpts': [{'passage': 'p1', 'text': text}]}
            for key, text in enumerate(texts, 1)]}, references=references, work={})


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['point', 'gap'])
async def test_final_review_projects_literal_focus_and_retained_objections_to_existing_query_contract(monkeypatch, kind):
    wire = originals()
    assertion = ('The permit cannot terminate.' if kind == 'point'
        else 'The exact triggering event for termination is absent from the supplied excerpts.')
    previous = 'The earlier proposal omitted an exception.'
    objection = 'Check the triggering event in the operative provision.'
    comment = 'The exception may narrow the apparent permission.'
    concern = {'previous_statements': [previous], 'issues': [
        {'instruction': objection, 'original_refs': [2], 'reviewer_notes': [
            {'comment': comment, 'originals': [wire.references[2]]}]}]}
    point = AssessmentPoint(statement=assertion,
        evidence=[AssessmentEvidence(**wire.references[1], role='support')])
    answer = AssessmentOutcome(status='partial', points=[point] if kind == 'point' else [],
        limitations=[] if kind == 'point' else [assertion])
    captured = []

    class Captured(Exception):
        pass

    async def select(service, current, task, seconds, **kwargs):
        captured.append((json.loads(task), retrieval._queries(current, task), kwargs['required_refs']))
        raise Captured

    class NoProvider:
        async def complete(self, *args, **kwargs):
            pytest.fail('This contract check stops at local selection before any reviewer call')

    monkeypatch.setattr(packing, 'select_evidence', select)
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=1, apertus_provider='swisscom'),
        model_client=NoProvider())
    before = deepcopy(wire.__dict__), answer.model_dump(), deepcopy(concern)
    with pytest.raises(Captured):
        await reasoned_review(service, wire, answer, 60, concerns={('P0' if kind == 'point' else 'L0'): concern})
    task, queries, required = captured[0]
    assert task['original_question'] == wire.input['original_question']
    assert 'requested_part' not in task, 'A generated assertion is never promoted to a user requirement'
    assert task['correction_target']['previous_statement'] == assertion
    assert queries[0] == assertion
    assert all(text in queries for text in (comment, objection, previous, wire.input['original_question']))
    assert queries.index(comment) < queries.index(wire.input['original_question'])
    assert not any(wire.references[2]['quote'] in query for query in queries), 'Originals remain evidence, not serialized query fields'
    assert set(required) == ({1, 2} if kind == 'point' else {2})
    assert (wire.__dict__, answer.model_dump(), concern) == before


@pytest.mark.asyncio
async def test_changed_review_focus_or_concern_invalidates_selection_but_keeps_mandatory_original(monkeypatch):
    wire, checkpoints, seen = originals(), {}, []
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=2100))

    async def rank(service, current, task, seconds, **kwargs):
        queries = retrieval._queries(current, task)
        seen.append(queries)
        target = 3 if queries[0] == 'The exception is missing.' else 1
        return {'rankings': [{'query': query, 'references': list(current.references),
            'scores': {key: 1 if key == target else 0 for key in current.references}} for query in queries],
            'coverage': {'method': 'scripted_rank_contract', 'semantic_status': 'not_evaluated'}}

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    def task(assertion, concern='Check the earlier objection.'):
        return json.dumps({'original_question': wire.input['original_question'],
            'correction_target': {'previous_statement': assertion, 'validation_errors': [{'reason': concern}]}})

    async def select(value):
        return await packing.select_evidence(service, wire, value, 60, required_refs=[2],
            checkpoints=checkpoints, request_size=lambda refs: 100 + 1000 * len(refs))

    before = deepcopy(wire.__dict__)
    first = await select(task('The termination event is missing.'))
    assert set(first) == {1, 2}
    assert await select(task('The termination event is missing.')) == first and len(seen) == 1
    assert set(await select(task('The exception is missing.'))) == {2, 3} and len(seen) == 2
    assert set(await select(task('The exception is missing.', 'Recheck a different retained objection.'))) == {2, 3}
    assert len(seen) == 3 and wire.__dict__ == before
    assert checkpoints['retrieval_coverage']['absence_established'] is False
    monkeypatch.setattr(retrieval, 'POLICY', 'revised-query-roles')
    assert set(await select(task('The exception is missing.', 'Recheck a different retained objection.'))) == {2, 3}
    assert len(seen) == 4, 'A changed query policy cannot reuse the previous selected packet'


@pytest.mark.asyncio
@pytest.mark.parametrize('signal', ['fast_not_established', 'fast_contradicted'])
async def test_fast_advisory_stays_in_review_but_does_not_compete_with_literal_retrieval(monkeypatch, signal):
    from helvetic_lens.research_final_review import FAST_ADVISORY

    wire = originals()
    question = 'Who can operate the equipment? When does the permit end? Which records must be kept?'
    wire.input['original_question'] = question
    assertion = 'The permit cannot terminate. The operator can surrender it.'
    comment = 'The surrender condition applies only to the permit operator.'
    instruction = 'Compare the termination provision with the claimed permanent permission.'
    concern = {'previous_statements': [assertion], 'issues': [
        {'signal': signal, 'instruction': FAST_ADVISORY, 'original_refs': [2],
            'reviewer_notes': [{'comment': comment, 'originals': [wire.references[2]]}]},
        {'signal': signal, 'instruction': instruction, 'original_refs': [3]}]}
    answer = AssessmentOutcome(status='possible_answer', points=[AssessmentPoint(statement=assertion,
        evidence=[AssessmentEvidence(**wire.references[1], role='support')])], limitations=[])
    before = deepcopy(wire.__dict__), answer.model_dump(), deepcopy(concern)
    captured = []

    class Captured(Exception):
        pass

    async def select(service, current, task, seconds, **kwargs):
        captured.append((json.loads(task), retrieval._queries(current, task), kwargs['required_refs']))
        return deepcopy(current.references)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            issues = payload['prior_review_concerns']['concerns']
            assert issues['C0']['instruction'] == FAST_ADVISORY
            assert issues['C0']['reviewer_notes'][0]['comment'] == comment
            assert issues['C1']['instruction'] == instruction
            raise Captured

    monkeypatch.setattr(packing, 'select_evidence', select)
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000, apertus_provider='swisscom',
        apertus_max_tokens=4096), model_client=Model())
    with pytest.raises(Captured):
        await reasoned_review(service, wire, answer, 60, concerns={'P0': concern})
    task, queries, required = captured[0]
    assert queries == [assertion, 'The permit cannot terminate.', 'The operator can surrender it.',
        comment, instruction, question]
    assert task['original_question'] == question and 'requested_part' not in task
    assert FAST_ADVISORY not in json.dumps(task)
    assert set(required) == {1, 2, 3}
    assert (wire.__dict__, answer.model_dump(), concern) == before
