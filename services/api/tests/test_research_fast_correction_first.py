"""Advisory negatives get one original-backed correction before factual review."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import witnessed_review
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_parts as parts
from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_operations import fingerprint


def setup(monkeypatch, mode, *, slots=False):
    texts, work, wire, parsed = fixture(slots=slots)
    revised = 'South Survey maintains the archive subject to the published access conditions.'
    wire.references[5] = {'source_id': 'registry', 'locator': 'p5', 'quote': revised}
    events, failed, saved = [], set(), {}

    async def fast(settings, work, wire, answer, *args, **kwargs):
        return {'status': 'checked', 'decisions': [], 'hints': [
            {'path': ['answer', 'points', i], 'review_signal': 'not_established'}
            for i, point in enumerate(answer.points) if point.statement == texts[1]]}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'decisions': [], 'hints': []}

    class Model:
        async def complete(self, system, serialized, **options):
            value = json.loads(serialized)
            if system.startswith(parts.SELECT):
                events.append(('select', None))
                return json.dumps({'citation_refs': {source['selection_key']: [
                    item['citation_ref'] for item in source['passages'] if 'citation_ref' in item]
                    for source in value['sources'] if 'selection_key' in source}})
            if system.startswith(parts.POINT_REPAIR):
                events.append(('writer', deepcopy(value['correction_target'])))
                assert value['correction_target']['previous_statement'] == texts[1]
                assert 'edit_scope' not in value['correction_target']
                issues = value['correction_target']['validation_errors']
                assert any(item['signal'] == 'fast_not_established' for item in issues)
                assert any(texts[1] in item['original_text'] for item in issues)
                if mode == 'writer_interrupt' and 'writer' not in failed:
                    failed.add('writer')
                    raise DomainError('Synthetic interruption', 503, 'model_rate_limited')
                if mode == 'empty':
                    return json.dumps({'points': []})
                target = texts[1] if mode in {'unchanged', 'invalid', 'unresolved'} else revised
                local = {item['text']: item['citation_ref'] for source in value['sources']
                    for item in source['passages'] if 'citation_ref' in item}
                return json.dumps({'points': [{'statement': target, 'evidence': [
                    {'citation_ref': 9999 if mode == 'invalid' else local[target], 'role': 'support'}]}]})
            key, item = next(iter(value['final_claims_and_gaps'].items()))
            text = item.get('statement', item.get('gap'))
            events.append(('review', text))
            if mode == 'review_interrupt' and text == revised and 'review' not in failed:
                failed.add('review')
                raise DomainError('Synthetic interruption', 503, 'model_rate_limited')
            if text in {texts[1], revised}:
                concerns = value['prior_review_concerns']['concerns']
                assert any(2 in issue['original_refs'] for issue in concerns.values())
                assert texts[1] in json.dumps(value['source_context']), 'Concern originals still reach factual review'
                if mode in {'bad_rewrite', 'unresolved'}:
                    verdict = {'verdict': 'contradicted' if text == revised else 'supported',
                        'reason': 'The original establishes the narrower statement.',
                        'citation_refs': value['selected_citation_refs']}
                    raw = {'overall': verdict, 'clauses': {key: verdict for key in value['assertion_clauses']},
                        'concern_checks': [{'id': key, 'outcome': 'cannot_assess' if mode == 'unresolved' else 'resolved',
                            'reason': 'This objection remains unresolved.' if mode == 'unresolved' else '',
                            'citation_refs': [] if mode == 'unresolved' else verdict['citation_refs']}
                            for key in concerns]}
                    return json.dumps(witnessed_review(raw, value))
            return response(value)

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', coverage)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    return texts, revised, work, wire, parsed, service, saved, events


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['rewrite', 'unchanged', 'empty', 'invalid', 'bad_rewrite', 'unresolved'])
async def test_advisory_correction_precedes_approval_and_preserves_false_negative_fallback(monkeypatch, mode):
    texts, revised, work, wire, parsed, service, saved, events = setup(monkeypatch, mode)
    original = parsed.mission_checkpoint.answer.model_dump()
    result = await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert [event[0] for event in events[:2]] == ['select', 'writer']
    assert sum(kind == 'writer' for kind, _ in events) == 1
    answer = parsed.mission_checkpoint.answer
    expected = revised if mode == 'rewrite' else texts[1]
    assert [point.statement for point in answer.points] == [texts[0], *([] if mode == 'unresolved' else [expected]), texts[2]]
    assert answer.points[0].model_dump() == original['points'][0]
    assert answer.points[-1].model_dump() == original['points'][2]
    assert not any('not validated' in gap or 'could not be validated' in gap for gap in answer.limitations)
    reviews = [text for kind, text in events if kind == 'review']
    assert reviews.count(texts[0]) == reviews.count(texts[2]) == 1
    if mode == 'rewrite':
        assert texts[1] not in reviews and revised in reviews
    if mode == 'bad_rewrite':
        assert reviews.index(revised) < reviews.index(texts[1]), 'A rejected rewrite restores and reviews the original'
    if mode == 'unresolved':
        assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'unresolved_concern'}]
    plan = saved['final_correction_round']
    assert plan['ordinary_planned'] and plan['completed'] == len(plan['tasks']) == 1
    assert all(observation['hint']['review_signal'] not in {'fast_not_established', 'fast_contradicted'}
        for observation in plan['observations']), 'Advisory signals never become retained factual defects'
    # Completed planning and proposal receipts cannot buy another correction.
    before = deepcopy(events)
    await final.finalize(service, work, wire, parsed, 90, checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert sum(kind == 'writer' for kind, _ in events) == 1
    assert [event for event in events[len(before):] if event[0] == 'review'] == (
        [('review', texts[3])] if mode == 'unresolved' else []), 'Only changed-subset gap coverage needs a new check'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,slots', [('writer_interrupt', False), ('writer_interrupt', True), ('review_interrupt', False)])
async def test_interrupted_advisory_plan_preserves_owned_target_and_completed_siblings(monkeypatch, mode, slots):
    texts, revised, work, wire, parsed, service, saved, events = setup(monkeypatch, mode, slots=slots)
    original = parsed.mission_checkpoint.answer.model_dump()
    with pytest.raises(DomainError) as error:
        await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'model_rate_limited'
    plan = saved['final_correction_round']
    task = plan['tasks'][0]
    owner = 'R0' if slots else None
    assert task['points'] == [fingerprint({'request_key': owner, 'point': original['points'][1]})]
    assert task['fallback']['point'] == original['points'][1]
    assert task['prior_concerns']['issues'][0]['original_text'] == [texts[1]]
    assert not plan['ordinary_planned']
    assert plan['completed'] == (0 if mode == 'writer_interrupt' else 1)
    if mode == 'writer_interrupt':
        assert parsed.mission_checkpoint.answer.model_dump() == original
        assert not any(kind == 'review' for kind, _ in events)
    saved = json.loads(json.dumps(saved))
    await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], revised, texts[2]]
    assert sum(kind == 'select' for kind, _ in events) == 1
    assert sum(kind == 'writer' for kind, _ in events) == (2 if mode == 'writer_interrupt' else 1)
    assert sum(event == ('review', texts[0]) for event in events) == 1
    assert sum(event == ('review', texts[2]) for event in events) == 1
    assert ('review', texts[1]) not in events


@pytest.mark.asyncio
async def test_legacy_completed_plan_cannot_bypass_current_advisory_correction(monkeypatch):
    texts, revised, work, wire, parsed, service, saved, events = setup(monkeypatch, 'rewrite')
    saved['final_correction_round'] = {'contract': 'literal-request-repair/v1',
        'point_concern_contract': 'point-task-concerns/v1', 'tasks': [], 'completed': 0,
        'receipts': [], 'observations': []}
    # Keep a real completed sibling proof in the old plan's private cache.
    sibling = parsed.mission_checkpoint.answer.model_copy(update={'points': [parsed.mission_checkpoint.answer.points[0]],
        'limitations': []})
    await final.reasoned_review(service, wire, sibling, 60, checkpoints=saved.setdefault('final_reviews', {}))
    old_proofs = {key: deepcopy(value) for key, value in saved['final_reviews'].items() if key.startswith('clauses:')}
    events.clear()
    await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert events[0][0] == 'select' and events[1][0] == 'writer'
    assert ('review', texts[0]) not in events, 'Current exact sibling proof survives the local plan upgrade'
    assert parsed.mission_checkpoint.answer.points[1].statement == revised
    assert saved['previous_final_correction_round']['completed'] == 0
    assert saved['final_correction_round']['fast_correction_policy'] == final.FAST_CORRECTION_PLAN
    assert all(saved['final_reviews'][key] == value for key, value in old_proofs.items())


@pytest.mark.asyncio
async def test_unavailable_fast_signal_is_not_repurchased_or_treated_as_negative(monkeypatch):
    texts, _, work, wire, parsed, service, saved, _ = setup(monkeypatch, 'empty')
    fast_calls, reviews = [], []

    async def unavailable(*args, **kwargs):
        fast_calls.append(True)
        return {'status': 'partial', 'hints': [], 'decisions': [{'choice': 'unavailable'}]}

    class Model:
        async def complete(self, system, serialized, **kwargs):
            value = json.loads(serialized)
            assert 'final_claims_and_gaps' in value, 'Unavailable advisory work cannot trigger a rewrite'
            reviews.append(next(iter(value['final_claims_and_gaps'])))
            return response(value)

    monkeypatch.setattr(audit, 'audit_points', unavailable)
    service.model_client = Model()
    await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert fast_calls == [True] and reviews == ['P0', 'P1', 'P2', 'L0']
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == texts[:3]
    assert saved['final_correction_round']['tasks'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['research_evidence_group_too_large', 'research_evidence_scope_invalid'])
async def test_advisory_packing_falls_back_but_current_scope_failure_propagates(monkeypatch, code):
    texts, _, work, wire, parsed, service, saved, events = setup(monkeypatch, 'empty')
    original = parsed.mission_checkpoint.answer.model_dump()
    attempts = []

    async def unavailable(*args, **kwargs):
        attempts.append(deepcopy(kwargs['correction']))
        raise DomainError('Synthetic local evidence boundary', 503, code)

    monkeypatch.setattr(final, 'answer_request', unavailable)
    if code == 'research_evidence_scope_invalid':
        with pytest.raises(DomainError) as error:
            await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert error.value.code == code and events == []
        assert saved['final_correction_round']['completed'] == 0
    else:
        await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert saved['final_correction_round']['receipts'][0]['status'] == 'unreviewable_citations'
        assert ('review', texts[1]) in events, 'The unmodified original still requires factual review'
    assert len(attempts) == 1 and parsed.mission_checkpoint.answer.points[1].model_dump() == original['points'][1]
