from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable


@pytest.mark.asyncio
async def test_focused_review_finds_late_counterexample_without_promoting_decisions_to_evidence(monkeypatch):
    calls = []
    witness = 'The fictional decision was adopted on 12 March 2005.'
    class Engine:
        async def choose(self, state, instructions, criteria):
            calls.append(state)
            if 'statement' in state:
                assert state['passages'] == ['Resolution number 1']
                choice = 'not_established'
            else:
                choice = next(key for key in criteria if key != 'none') if any(p['text'] == witness for p in state['passages']) else 'none'
            return Decision('jev', 'test', choice, {choice: 1.0}, 1, 1, 1, 10, 1)
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine()})
    wire = SimpleNamespace(references={i: {'quote': 'Public background. ' * 25} for i in range(1, 12)})
    wire.references[12] = {'quote': witness}
    answer = SimpleNamespace(points=[SimpleNamespace(statement='The resolution was published in 2005.',
        evidence=[SimpleNamespace(quote='Resolution number 1')])], limitations=[
            'The supplied sources do not give the exact adoption date.', 'The adoption year is not provided.'])
    result = await review.audit(Settings(_env_file=None), {'input': {'sources': [{'kind': 'public_source'}]}}, wire, answer, 60)
    assert result['status'] == 'checked' and result['points_checked'] == 1
    assert result['limitation_batches_checked'] > 1
    assert [hint['path'] for hint in result['hints']] == [['answer', 'points', 0], ['answer', 'limitations', 0], ['answer', 'limitations', 1]]
    assert any(p['citation_ref'] == 12 and p['text'] == witness for p in result['hints'][1]['original_windows'])
    assert sorted({p['citation_ref'] for call in calls if 'statement' not in call for p in call['passages']}) == list(range(1, 13))
    assert answer.points[0].statement == 'The resolution was published in 2005.'  # Hints never rewrite facts.


@pytest.mark.asyncio
async def test_private_pack_never_enters_hosted_answer_audit(monkeypatch):
    def forbidden(settings):
        pytest.fail('Private evidence must not leave the configured synthesis boundary')
    monkeypatch.setattr(review.decision, 'engines', forbidden)
    result = await review.audit(Settings(_env_file=None), {'input': {'sources': [{'kind': 'uploaded_file'}]}}, None, None, 60)
    assert result['status'] == 'not_applicable' and not result['hints']


@pytest.mark.asyncio
async def test_unavailable_audit_is_explicit_and_never_claims_support(monkeypatch):
    class Unavailable:
        async def choose(self, *args):
            raise DecisionUnavailable('quota')
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Unavailable(), 'laya': Unavailable()})
    answer = SimpleNamespace(points=[SimpleNamespace(statement='A proposed finding.', evidence=[SimpleNamespace(quote='An original passage.')])], limitations=[])
    result = await review.audit(Settings(_env_file=None), {'input': {'sources': [{'kind': 'public_source'}]}}, SimpleNamespace(references={}), answer, 60)
    assert result['status'] == 'partial' and result['points_checked'] == 0
    assert result['hints'] == [] and result['decisions'][0]['choice'] == 'unavailable'
    assert {error['engine'] for error in result['decisions'][0]['fallback_errors']} == {'jev', 'laya'}


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict', ['supported', 'not_established', 'contradicted', 'unavailable'])
async def test_context_completion_requires_same_original_and_entailment(monkeypatch, verdict):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_gateway import answer_quantity_errors
    calls = []
    class Engine:
        async def choose(self, state, *args):
            calls.append(state)
            assert [ref['quote'] for ref in state['passages']] == ['The committee adopted the revised unit.', 'Committee decision (2005)']
            assert all(ref['source_id'] == 'a' for ref in state['passages'])
            if verdict == 'unavailable':
                raise DecisionUnavailable('quota')
            return Decision('jev', 'test', verdict, {verdict: 1}, 1, 1, 1, 1, 1)
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    answer = AssessmentOutcome(status='possible_answer', limitations=['The implementation date remains unknown.'],
        points=[{'statement': 'The committee adopted the revised unit in 2005.', 'evidence': [
            {'source_id': 'a', 'locator': 'p2', 'quote': 'The committee adopted the revised unit.', 'role': 'support'}]}])
    wire = SimpleNamespace(references={1: {'source_id': 'a', 'locator': 'p1', 'quote': 'Committee decision (2005)'},
        2: {'source_id': 'b', 'locator': 'p1', 'quote': 'Unrelated record (2005)'}})
    receipt = await review.complete_citation_context(Settings(_env_file=None),
        {'input': {'sources': [{'kind': 'public_source'}]}}, wire, answer, 60)
    assert calls
    assert answer.points[0].statement == 'The committee adopted the revised unit in 2005.'
    assert len(answer.points[0].evidence) == (2 if verdict == 'supported' else 1)
    assert bool(answer_quantity_errors(answer)) == (verdict != 'supported')
    if verdict == 'supported':
        assert answer.points[0].evidence[1].role == 'context'
        assert receipt[0]['added_context'][0]['source_id'] == 'a'


@pytest.mark.asyncio
@pytest.mark.parametrize('sources', [[], [{'kind': 'uploaded_file'}]])
async def test_context_completion_never_sends_private_or_empty_pack(monkeypatch, sources):
    monkeypatch.setattr(review.decision, 'engines', lambda settings: pytest.fail('No external call authorized'))
    assert await review.complete_citation_context(None, {'input': {'sources': sources}}, None, None, 60) == []


@pytest.mark.asyncio
async def test_single_point_repair_rebinds_local_refs_without_changing_other_findings():
    from helvetic_lens.product_exploration import AssessmentOutcome
    refs = {77: {'source_id': 'a', 'locator': 'p1', 'quote': 'The fictional record was published in 1900.'}}
    answer = AssessmentOutcome(status='possible_answer', limitations=[], points=[
        {'statement': 'The fictional record was published in 1999.', 'evidence': [{**refs[77], 'role': 'support'}]},
        {'statement': 'The record concerns a fictional event.', 'evidence': [{**refs[77], 'role': 'context'}]}])
    unchanged = answer.points[1].model_copy(deep=True)
    class Model:
        async def complete(self, system, text, **kwargs):
            import json
            state = json.loads(text)
            assert state['requested_part'] == 'When was the record published?'
            assert state['original_windows'][0]['citation_ref'] == 1
            assert state['original_windows'][0]['locator'] == 'p1'
            return json.dumps({'evidence': [{'citation_ref': 1, 'role': 'support'}],
                'statement': 'The fictional record was published in 1900.'})
    result = await review.repair_points(SimpleNamespace(model_client=Model()), SimpleNamespace(references=refs, request_keys={'r2': 'When was the record published?'}, point_requests=['r2', 'r2']), answer, 60)
    assert result and answer.points[0].evidence[0].quote == refs[77]['quote']
    assert answer.points[1] == unchanged
    assert '1900' in answer.points[0].statement


@pytest.mark.asyncio
@pytest.mark.parametrize('matched', [False, True])
@pytest.mark.parametrize('timeout', [False, True])
async def test_original_reading_requires_link_witness_and_retains_current_answer(monkeypatch, matched, timeout):
    from helvetic_lens.product_research_mission import Checkpoint
    source_id = 'a' * 36
    quote = 'The comparison comes from the Original Agency research paper.'
    ref = {'source_id': source_id, 'locator': 'p1', 'quote': quote}
    checkpoint = Checkpoint(answer={'status': 'possible_answer', 'limitations': [],
        'points': [{'statement': 'A tentative comparison.', 'evidence': [{**ref, 'role': 'context'}]}]},
        action='finish', reason='The available retelling explains the comparison.')
    source = {'id': source_id, 'url': 'https://example.org/retelling', 'title': 'Retelling',
        'discovery_links': [{'url': 'https://example.org/original', 'kind': 'document', 'title': 'Original Agency paper',
            'context': quote if matched else 'Unretained anchor text is never an original quote.'}]}
    wire = SimpleNamespace(references={1: ref}, input={'sources': [source], 'research_mission': {'attempted_queries': []}})
    calls = []
    now = [0]
    monkeypatch.setattr(review, 'monotonic', lambda: now[0])
    class Engine:
        async def choose(self, state, system, criteria):
            calls.append(state)
            if timeout:
                now[0] = 12
                raise DecisionUnavailable('timeout')
            assert state['unread_links'][0]['witness'] == ref
            return Decision('jev', 'test', '0', {'0': 1}, 1, 1, 1, 1, 1)
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    work = {'input': {'sources': [{'kind': 'public_source'}], 'original_question': 'Compare the definitions using original sources.'}}
    saved = checkpoint.answer.points[0].model_copy(deep=True)
    await review.original_check(Settings(_env_file=None), work, wire, checkpoint, 14 if timeout else 60)
    assert checkpoint.answer.points[0] == saved
    if matched and timeout:
        assert len(calls) == 1 and checkpoint.action == 'finish'
    elif matched:
        assert checkpoint.action == 'continue' and checkpoint.answer.status == 'partial'
        assert checkpoint.next_checks[0].query == 'https://example.org/original'
        assert checkpoint.next_checks[0].catalogues == []
        assert checkpoint.next_checks[0].quote == quote
    else:
        assert not calls and checkpoint.action == 'finish'
