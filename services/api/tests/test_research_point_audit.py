from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable


def point(statement, *quotes):
    return SimpleNamespace(statement=statement, evidence=[SimpleNamespace(quote=quote) for quote in quotes])


def inputs(*points):
    work = {'input': {'sources': [{'kind': 'public_source'}], 'original_question': 'Compare the fictional records.'}}
    wire = SimpleNamespace(references={i + 1: {'quote': ref.quote}
        for i, ref in enumerate(ref for item in points for ref in item.evidence)})
    answer = SimpleNamespace(points=list(points), limitations=['A separate question remains unanswered.'])
    return work, wire, answer


class Engine:
    name, model, url, key = 'jev', 'configured-test', 'https://decision.example', 'private-secret'

    def __init__(self, choices):
        self.choices, self.calls = iter(choices), []

    async def choose(self, state, instructions, criteria):
        self.calls.append(deepcopy(state))
        assert instructions == review.POINT_SYSTEM and criteria == review.POINT_CRITERIA
        value = next(self.choices)
        if isinstance(value, Exception):
            raise value
        return Decision(self.name, 'reported-test', value, {value: 1}, 1, 1, 1, 10, 1)


@pytest.mark.asyncio
async def test_point_audit_returns_advisory_signals_and_all_selected_quotes_without_other_audits(monkeypatch):
    engine = Engine(['not_established', 'contradicted', 'supported'])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': engine})
    quotes = tuple(f'Fictional record clause {i}.' for i in range(8))
    work, wire, answer = inputs(point('The record establishes an unsupported global total.', *quotes),
        point('The standard was adopted after publication.', 'The standard was adopted before publication.'),
        point('The operator is Acme.', 'The operator is Acme.'))
    before, checkpoints, saved = deepcopy(answer), {}, []
    result = await review.audit_points(Settings(_env_file=None), work, wire, answer, 60,
        checkpoints=checkpoints, on_progress=lambda: saved.append(deepcopy(checkpoints)))
    assert result['status'] == 'checked' and result['points_checked'] == 3
    assert [hint['review_signal'] for hint in result['hints']] == ['not_established', 'contradicted']
    assert [hint['path'] for hint in result['hints']] == [['answer', 'points', 0], ['answer', 'points', 1]]
    assert result['hints'][0]['original_windows'] == [{'text': quote} for quote in quotes]
    assert len(result['hints'][0]['candidate_windows']) == 5
    assert engine.calls[0] == {'statement': answer.points[0].statement, 'passages': list(quotes)}
    assert len(engine.calls) == 3 and answer == before
    assert len(saved) == 3 and len(checkpoints['point_decisions']) == 3
    assert all('statement' not in receipt and 'passages' not in receipt
        for receipt in checkpoints['point_decisions'].values())
    assert 'private-secret' not in repr(checkpoints)


@pytest.mark.asyncio
@pytest.mark.parametrize('sources', [[], [{'kind': 'uploaded_file'}],
    [{'kind': 'public_source'}, {'kind': 'uploaded_file'}]])
async def test_point_audit_preserves_public_only_boundary_even_with_cached_results(monkeypatch, sources):
    monkeypatch.setattr(review.decision, 'engines', lambda settings: pytest.fail('Private evidence must not leave the boundary'))
    checkpoints = {'point_decisions': {'retained': {'choice': 'supported'}}}
    before = deepcopy(checkpoints)
    result = await review.audit_points(None, {'input': {'sources': sources}}, None, None, 60, checkpoints=checkpoints)
    assert result['status'] == 'not_applicable' and result['hints'] == [] and result['decisions'] == []
    assert checkpoints == before


@pytest.mark.asyncio
async def test_exact_point_cache_survives_reordering_and_rebinds_current_witnesses(monkeypatch):
    engine = Engine(['not_established', 'supported'])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': engine})
    work, wire, answer = inputs(point('An unsupported conclusion.', 'First quote.', 'Second quote.'),
        point('A supported conclusion.', 'A supporting quote.'))
    checkpoints = {}
    await review.audit_points(Settings(_env_file=None), work, wire, answer, 60, checkpoints=checkpoints)
    answer.points.reverse()
    wire.references = {91: {'quote': 'First quote.'}, 92: {'quote': 'Second quote.'}}
    result = await review.audit_points(Settings(_env_file=None), work, wire, answer, 0, checkpoints=checkpoints)
    assert len(engine.calls) == 2 and result['status'] == 'checked'
    assert all(receipt['reused'] for receipt in result['decisions'])
    assert result['hints'][0]['path'] == ['answer', 'points', 1]
    assert {item['citation_ref'] for item in result['hints'][0]['candidate_windows']} == {91, 92}
    # A caller modifying its copy cannot corrupt the private completed receipt.
    result['decisions'][0]['choice'] = 'contradicted'
    again = await review.audit_points(Settings(_env_file=None), work, wire, answer, 0, checkpoints=checkpoints)
    assert again['decisions'][0]['choice'] == 'supported'


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['statement', 'quote', 'quote_order', 'policy', 'model', 'endpoint', 'configured'])
async def test_changed_point_policy_or_engine_cannot_reuse_a_completed_signal(monkeypatch, change):
    engine = Engine(['supported', 'not_established'])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': engine})
    work, wire, answer = inputs(point('A proposed conclusion.', 'First quotation.', 'Second quotation.'))
    settings, checkpoints = Settings(_env_file=None), {}
    await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    if change == 'statement':
        answer.points[0].statement += ' An additional assertion.'
    elif change == 'quote':
        answer.points[0].evidence[0].quote += ' A qualification.'
    elif change == 'quote_order':
        answer.points[0].evidence.reverse()
    elif change == 'policy':
        monkeypatch.setattr(review, 'POINT_SYSTEM', review.POINT_SYSTEM + '\nNew policy qualification.')
    elif change == 'model':
        engine.model = 'different-configured-model'
    elif change == 'endpoint':
        engine.url = 'https://different-decision.example'
    else:
        engine.key = ''
    result = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    assert len(engine.calls) == 2 and len(checkpoints['point_decisions']) == 2
    assert result['hints'][0]['review_signal'] == 'not_established'


@pytest.mark.asyncio
async def test_failed_point_retries_only_unfinished_work_and_fallback_keeps_all_quotes(monkeypatch):
    jev = Engine(['supported', DecisionUnavailable('quota'), 'not_established'])
    laya = Engine([TimeoutError()])
    laya.name, laya.model, laya.url = 'laya', 'multilingual', 'http://localhost/v1/systemone'
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    work, wire, answer = inputs(point('First point.', 'First original.'), point('Second point.', 'Second original.'))
    settings, checkpoints = Settings(_env_file=None), {}
    first = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    assert first['status'] == 'partial' and first['points_checked'] == 1
    assert first['hints'] == [] and len(checkpoints['point_decisions']) == 1
    assert first['decisions'][1]['fallback_errors'] == [
        {'engine': 'jev', 'code': 'quota'}, {'engine': 'laya', 'code': 'timeout'}]
    assert laya.calls == [{'statement': 'Second point.', 'passages': ['Second original.']}]
    second = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    assert second['status'] == 'checked' and second['points_checked'] == 2
    assert len(jev.calls) == 3 and len(laya.calls) == 1
    assert second['decisions'][0]['reused'] and second['hints'][0]['path'] == ['answer', 'points', 1]


@pytest.mark.asyncio
async def test_laya_fallback_success_is_cached_as_advisory_not_a_factual_rewrite(monkeypatch):
    jev, laya = Engine([DecisionUnavailable('unavailable')]), Engine(['contradicted'])
    laya.name, laya.model = 'laya', 'multilingual'
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    work, wire, answer = inputs(point('A retained claim.', 'A contrary original.'))
    checkpoints, settings = {}, Settings(_env_file=None)
    first = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    second = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    assert first['decisions'][0]['engine'] == 'laya'
    assert second['decisions'][0]['reused'] and len(jev.calls) == len(laya.calls) == 1
    assert answer.points[0].statement == 'A retained claim.'


@pytest.mark.asyncio
async def test_oversized_laya_input_is_not_truncated_or_cached(monkeypatch):
    jev, laya = Engine([DecisionUnavailable('quota')]), Engine([])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    quote = 'All original text must remain present. ' * 150
    work, wire, answer = inputs(point('A claim with a long witness.', quote))
    checkpoints = {}
    result = await review.audit_points(Settings(_env_file=None), work, wire, answer, 60, checkpoints=checkpoints)
    assert jev.calls[0]['passages'] == [quote] and not laya.calls
    assert result['status'] == 'partial' and result['hints'] == []
    assert result['decisions'][0]['fallback_errors'][-1] == {'engine': 'laya', 'code': 'input_does_not_fit'}
    assert checkpoints['point_decisions'] == {}


@pytest.mark.asyncio
async def test_point_checkpoint_is_saved_before_interruption_and_deadline_does_not_cache_unknown(monkeypatch):
    engine = Engine(['supported', 'supported'])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': engine})
    work, wire, answer = inputs(point('First point.', 'First original.'), point('Second point.', 'Second original.'))
    checkpoints, settings = {}, Settings(_env_file=None)

    def interrupted():
        raise RuntimeError('Simulated worker interruption')

    with pytest.raises(RuntimeError, match='Simulated worker interruption'):
        await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints, on_progress=interrupted)
    assert len(checkpoints['point_decisions']) == 1
    waiting = await review.audit_points(settings, work, wire, answer, 0, checkpoints=checkpoints)
    assert waiting['status'] == 'partial' and waiting['points_checked'] == 1 and len(engine.calls) == 1
    assert len(checkpoints['point_decisions']) == 1
    done = await review.audit_points(settings, work, wire, answer, 60, checkpoints=checkpoints)
    assert done['status'] == 'checked' and len(engine.calls) == 2


@pytest.mark.asyncio
async def test_deadline_before_fallback_retains_the_actual_failed_attempt(monkeypatch):
    clock = [0]
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class SlowUnavailable(Engine):
        async def choose(self, *args):
            clock[0] += 8
            raise DecisionUnavailable('quota')

    laya = Engine([])
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': SlowUnavailable([]), 'laya': laya})
    work, wire, answer = inputs(point('An unchecked point.', 'An original quotation.'))
    checkpoints = {}
    result = await review.audit_points(Settings(_env_file=None), work, wire, answer, 20, checkpoints=checkpoints)
    assert result['status'] == 'partial' and result['hints'] == [] and not laya.calls
    assert result['decisions'][0]['fallback_errors'] == [
        {'engine': 'jev', 'code': 'quota'}, {'engine': 'laya', 'code': 'step_deadline'}]
    assert checkpoints['point_decisions'] == {}


@pytest.mark.asyncio
async def test_slow_outage_stops_after_one_fallback_pair_but_reuses_later_cached_points(monkeypatch):
    clock, outage = [0], [False]
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class SlowEngine(Engine):
        async def choose(self, state, instructions, criteria):
            self.calls.append(deepcopy(state))
            if outage[0]:
                clock[0] += 12
                raise TimeoutError()
            return Decision(self.name, 'reported-test', 'supported', {'supported': 1}, 1, 1, 1, 10, 1)

    jev, laya = SlowEngine([]), SlowEngine([])
    laya.name, laya.model, laya.url = 'laya', 'multilingual', 'http://localhost/v1/systemone'
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    work, wire, answer = inputs(*(point(f'Point {i}.', f'Original {i}.') for i in range(8)))
    settings, checkpoints = Settings(_env_file=None), {}
    retained = SimpleNamespace(points=[answer.points[6]])
    await review.audit_points(settings, work, wire, retained, 90, checkpoints=checkpoints)
    jev.calls.clear()
    outage[0] = True
    before = deepcopy(checkpoints)
    result = await review.audit_points(settings, work, wire, answer, 90, checkpoints=checkpoints)
    assert len(jev.calls) == len(laya.calls) == 1 and clock[0] == 24
    assert 90 - clock[0] == 66  # The deeper review retains most of its time.
    assert result['status'] == 'partial' and result['points_checked'] == 1 and result['hints'] == []
    assert len(result['decisions']) == 8 and result['decisions'][6]['reused']
    assert result['decisions'][0]['fallback_errors'] == [
        {'engine': 'jev', 'code': 'timeout'}, {'engine': 'laya', 'code': 'timeout'}]
    assert all(receipt['choice'] == 'unavailable' for i, receipt in enumerate(result['decisions']) if i != 6)
    assert all(result['decisions'][i]['fallback_errors'] == [{'code': 'earlier_point_unavailable'}]
        for i in (1, 2, 3, 4, 5, 7))
    assert checkpoints == before  # Neither failed nor skipped points became successful cache entries.
    outage[0] = False
    resumed = await review.audit_points(settings, work, wire, answer, 90, checkpoints=checkpoints)
    assert resumed['status'] == 'checked' and resumed['points_checked'] == 8
    assert len(jev.calls) == 8 and len(laya.calls) == 1


@pytest.mark.asyncio
async def test_eight_request_coverage_outage_preserves_time_after_point_audit(monkeypatch):
    clock, calls = [0], []
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class SlowUnavailable(Engine):
        async def choose(self, state, instructions, criteria):
            calls.append((self.name, deepcopy(state)))
            clock[0] += 12
            raise TimeoutError()

    jev, laya = SlowUnavailable([]), SlowUnavailable([])
    laya.name = 'laya'
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    work, wire, answer = inputs(*(point(f'Point {i}.', f'Original {i}.') for i in range(8)))
    work['input']['original_question'] = ' '.join(f'What is metric {i}?' for i in range(8))
    wire.input = {'sources': [{'url': 'https://original.example'}]}
    assert len(review.explicit_requests(work['input']['original_question'])) == 8
    settings, checkpoints = Settings(_env_file=None), {}
    fast = await review.audit_points(settings, work, wire, answer, 90, checkpoints=checkpoints)
    coverage = await review.audit(settings, work, wire, answer, 90-clock[0], coverage_only=True)
    assert clock[0] == 48 and 90-clock[0] == 42
    assert [name for name, _state in calls] == ['jev', 'laya', 'jev', 'laya']
    assert [state['specific_request'] for _name, state in calls if 'specific_request' in state] == [
        'What is metric 0?', 'What is metric 0?']
    assert fast['status'] == coverage['status'] == 'partial'
    assert coverage['question_coverage'] is None and coverage['hints'] == []
    assert len(coverage['decisions']) == 8
    assert coverage['decisions'][0]['fallback_errors'] == [
        {'engine': 'jev', 'code': 'timeout'}, {'engine': 'laya', 'code': 'timeout'}]
    assert all(receipt['fallback_errors'] == [{'code': 'earlier_review_unavailable'}]
        for receipt in coverage['decisions'][1:])
    assert checkpoints['point_decisions'] == {}


@pytest.mark.asyncio
async def test_coverage_outage_retains_known_missing_request_but_does_not_invent_more(monkeypatch):
    clock, calls, outage = [0], [], [True]
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class CoverageEngine(Engine):
        async def choose(self, state, instructions, criteria):
            calls.append((self.name, deepcopy(state)))
            if not outage[0]:
                choice = 'covered'
            elif state['specific_request'] == 'Who operates it?':
                choice = 'missing'
            else:
                clock[0] += 12
                raise TimeoutError()
            return Decision(self.name, 'test', choice, {choice: 1}, 1, 1, 1, 10, 1)

    jev, laya = CoverageEngine([]), CoverageEngine([])
    laya.name = 'laya'
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': jev, 'laya': laya})
    work, wire, answer = inputs(point('A known result.', 'An original passage.'))
    work['input']['original_question'] = 'Who operates it? When was it adopted? When was it published?'
    wire.input = {'sources': [{'url': 'https://original.example'}]}
    settings = Settings(_env_file=None)
    result = await review.audit(settings, work, wire, answer, 90, coverage_only=True)
    assert result['status'] == 'partial' and result['question_coverage'] is None and clock[0] == 24
    assert len(calls) == 3
    assert [hint['user_request'] for hint in result['hints']] == ['Who operates it?']
    outage[0] = False
    recovered = await review.audit(settings, work, wire, answer, 90, coverage_only=True)
    assert recovered['status'] == 'checked' and recovered['question_coverage'] == 'covered'
    assert recovered['hints'] == [] and len(calls) == 6


@pytest.mark.asyncio
async def test_all_mode_does_not_restart_failed_engines_for_points_or_limitations(monkeypatch):
    clock, calls = [0], []
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class SlowUnavailable(Engine):
        async def choose(self, state, instructions, criteria):
            calls.append(deepcopy(state))
            clock[0] += 12
            raise TimeoutError()

    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': SlowUnavailable([]), 'laya': SlowUnavailable([])})
    work, wire, answer = inputs(point('A proposed result.', 'An original passage.'))
    work['input']['original_question'] = 'Who operates it? When was it adopted?'
    wire.input = {'sources': [{'url': 'https://original.example'}]}
    result = await review.audit(Settings(_env_file=None), work, wire, answer, 90)
    assert clock[0] == 24 and len(calls) == 2
    assert result['status'] == 'partial' and result['question_coverage'] is None
    assert result['points_checked'] == result['limitation_batches_checked'] == 0 and result['hints'] == []
