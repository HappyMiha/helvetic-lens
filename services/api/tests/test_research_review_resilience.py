"""Provider failure can defer exact assertions without certifying or losing them."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import witnessed_review

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_synthesis_resume import completed_work


def response(payload):
    key, item = next(iter(payload['final_claims_and_gaps'].items()))
    verdict = {'verdict': 'supported', 'reason': '',
        'citation_refs': payload.get('selected_citation_refs', [4])}
    value = {'overall': verdict, 'clauses': {key: verdict for key in payload['assertion_clauses']}}
    if 'gap' in item:
        value['gap_status'] = 'unresolved'
    if payload.get('prior_review_concerns'):
        value['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': '',
            'citation_refs': verdict['citation_refs']} for key in payload['prior_review_concerns']['concerns']]
    return json.dumps(witnessed_review(value, payload))


def fixture(*, slots=False):
    texts = ['North Survey operates the registry.', 'South Survey maintains the archive.',
        'The registry is available to the public.', 'Earlier archive custody is not recorded.']
    refs = {i: {'source_id': 'registry', 'locator': f'p{i}', 'quote': text} for i, text in enumerate(texts, 1)}
    answer = AssessmentOutcome(status='partial', points=[{'statement': text,
        'evidence': [{**refs[i], 'role': 'support'}]} for i, text in enumerate(texts[:3], 1)], limitations=[texts[3]])
    question = 'Who operates the registry and archive, is it public, and what remains unknown?'
    work = {'input': {'original_question': question, 'sources': [{'id': 'registry', 'kind': 'public_source'}]}}
    wire = SimpleNamespace(input=work['input'], references=refs, request_keys={'R0': question} if slots else {},
        point_requests=['R0'] * 3 if slots else [], response_slots={
            'R0': {'disposition': 'unresolved', 'remaining_gap': texts[3]}} if slots else {})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    return texts, work, wire, parsed


@pytest.mark.asyncio
async def test_timeout_retains_completed_work_and_gives_unattempted_assertions_the_next_step(monkeypatch):
    texts, _, wire, parsed = fixture()
    clock, calls, saved = [0], [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key == 'P0':
                clock[0] += 55
                raise DomainError('Synthetic upstream timeout', 504, 'model_upstream_timeout')
            return response(payload)

    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    first = await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 60, checkpoints=saved)
    assert calls == ['P0']
    assert first['pending_checks'][0]['reason'] == 'model_upstream_timeout'
    assert completed_work({'parts': {'final_reviews': saved}}) == {}, 'An unavailable receipt is not completed work'
    second = await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 60, checkpoints=saved)
    assert calls == ['P0', 'P1', 'P2', 'L0', 'P0']
    assert second['pending_checks'] == [{'item': 'P0', 'reason': 'model_upstream_timeout'}]
    assert len(completed_work({'parts': {'final_reviews': saved}})) == 3
    before = list(calls)
    deferred = await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 60,
        checkpoints=saved, defer_transient=True)
    assert calls == before and deferred['pending_checks'] == second['pending_checks']
    wire.input['original_question'] += ' Explain the responsible operators.'
    await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 60,
        checkpoints=saved, defer_transient=True)
    assert calls[len(before)] == 'P0', 'An old failed binding cannot defer a changed request'
    assert parsed.mission_checkpoint.answer.points[0].statement == texts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('slots', [False, True])
async def test_exhausted_review_can_publish_only_checked_subset_and_restore_full_private_draft(monkeypatch, slots):
    texts, work, wire, parsed = fixture(slots=slots)
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    old_slots, old_owners = deepcopy(wire.response_slots), list(wire.point_requests)
    failures, calls, coverage, saved = [True], [], [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if failures[0] and assertion in {texts[1], texts[3]}:
                raise DomainError('Synthetic upstream timeout', 504, 'model_upstream_timeout')
            return response(payload)

    async def point_audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage_audit(settings, work, wire, answer, *args, **kwargs):
        actual = [p.statement for p in answer.points]
        coverage.append(actual)
        missing = texts[1] not in actual
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered', 'decisions': [],
            'hints': [{'review_signal': 'requested_part_missing', 'user_request': work['input']['original_question']}] if missing else []}

    monkeypatch.setattr(audit, 'audit_points', point_audit)
    monkeypatch.setattr(audit, 'audit', coverage_audit)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as failure:
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert failure.value.code == 'model_upstream_timeout'
    assert calls == texts and parsed.mission_checkpoint.answer.model_dump() == original
    assert 'deferred_final_review' not in saved
    work['allow_checked_partial_delivery'] = True
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    delivered = parsed.mission_checkpoint.answer
    assert calls == texts, 'Exhausted exact bindings must not consume another timeout before qualification'
    assert [p.statement for p in delivered.points] == [texts[0], texts[2]]
    assert texts[3] not in delivered.limitations and review.DEFERRED_NOTICE in delivered.limitations
    assert delivered.status == 'partial' and result['question_coverage'] == 'missing'
    assert result['factual_review']['pending_checks'] == []
    assert result['deferred_checks'] == [{'item': 'P1', 'reason': 'model_upstream_timeout'},
        {'item': 'L0', 'reason': 'model_upstream_timeout'}]
    assert [texts[0], texts[2]] in coverage, 'Coverage must be reassessed on the actually delivered subset'
    assert texts[1] not in json.dumps(result) and texts[3] not in json.dumps(result)
    private = saved['deferred_final_review']
    assert private['status'] == 'qualified_delivery' and private['answer'] == original
    assert private['point_requests'] == old_owners and private['response_slots'] == old_slots
    assert private['source_binding'] and private['policy_fingerprint'] == review.POLICY

    # An ordinary exact-input retry resumes the original obligations, never the
    # smaller readable result; independently completed checks are still reused.
    work['retry_deferred_review'] = True
    failures[0] = False
    result = await review.finalize(service, work, wire, parsed, 90,
        checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert calls == [*texts, texts[1], texts[3]]
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert wire.point_requests == old_owners and wire.response_slots == old_slots
    assert 'deferred_checks' not in result


@pytest.mark.asyncio
@pytest.mark.parametrize('problem', ['no_checked_point', 'coverage_unavailable'])
async def test_qualified_delivery_still_requires_a_useful_checked_answer_and_subset_coverage(monkeypatch, problem):
    texts, work, wire, parsed = fixture()
    calls, saved = [], {}
    work['allow_checked_partial_delivery'] = True

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if problem == 'no_checked_point' or assertion == texts[1]:
                raise DomainError('Synthetic upstream timeout', 504, 'model_upstream_timeout')
            return response(payload)

    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(settings, work, wire, answer, *args, **kwargs):
        partial = problem == 'coverage_unavailable' and len(answer.points) < 3
        return {'status': 'partial' if partial else 'checked', 'hints': [],
            'question_coverage': None if partial else 'covered', 'decisions': []}

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', coverage)
    with pytest.raises(DomainError) as failure:
        await review.finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
            work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert failure.value.code in {'model_upstream_timeout', 'research_review_incomplete'}
    assert saved.get('deferred_final_review', {}).get('status') != 'qualified_delivery'


@pytest.mark.asyncio
async def test_nontransient_configuration_failure_is_not_an_unavailable_assertion():
    _, _, wire, parsed = fixture()
    saved = {}

    class Model:
        async def complete(self, *args, **kwargs):
            raise DomainError('Synthetic access denial', 502, 'model_access_denied')

    with pytest.raises(DomainError) as failure:
        await review.reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
            wire, parsed.mission_checkpoint.answer, 90, checkpoints=saved)
    assert failure.value.code == 'model_access_denied'
    assert not saved.get('transient_assertions') and not any(key.startswith('clauses:') for key in saved)
    assert completed_work({'parts': {'final_reviews': saved}}) == {}, 'Retrieval scope is not a completed factual check'
