"""Unreviewable citation layouts remain unapproved without starving other findings.

Scripted judgments exercise lifecycle and transport, not model semantic accuracy.
"""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_evidence_pack as pack
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint
from helvetic_lens.product_operations import fingerprint


def layout_fixture(monkeypatch, *, slots=False):
    texts, work, wire, parsed = fixture(slots=slots)
    for key, ref in wire.references.items():
        ref.update(source_id=f'original-{key}', locator='page-1-text-1-char-1')
        if key <= 3:
            parsed.mission_checkpoint.answer.points[key - 1].evidence = [type(
                parsed.mission_checkpoint.answer.points[key - 1].evidence[0])(**ref, role='support')]
    wire.references[5] = {'source_id': 'alternative', 'locator': 'page-1-text-1-char-1',
        'quote': 'South Survey maintains the archive under the governing terms.'}
    wire.references[6] = {'source_id': 'original-2', 'locator': 'page-1-text-2-char-1',
        'quote': 'The full governing qualification must remain with this statement. ' * 700}
    sources = {}
    for key, ref in wire.references.items():
        source = sources.setdefault(ref['source_id'], {'id': ref['source_id'], 'kind': 'public_source',
            'sha256': fingerprint(ref['source_id']), 'url': f'https://example.test/{ref["source_id"]}', 'excerpts': []})
        source['excerpts'].append({'passage': ref['locator'], 'text': ref['quote']})
    wire.input['sources'] = list(sources.values())
    calls = []

    async def rank(*args, **kwargs):
        calls.append('local-rank')
        return {'rankings': [{'query': texts[1], 'references': [5, 1, 3, 4],
            'scores': {5: 1, 1: .8, 3: .7, 4: .6}}], 'coverage': {'method': 'scripted-retained-ranks'}}

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    return texts, work, wire, parsed, calls


def audits(monkeypatch, target, coverage):
    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def cover(settings, work, wire, answer, *args, **kwargs):
        statements = [point.statement for point in answer.points]
        coverage.append(statements)
        missing = target not in statements
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered',
            'hints': [{'review_signal': 'requested_part_missing', 'user_request': work['input']['original_question']}]
                if missing else [], 'decisions': []}

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', cover)


@pytest.mark.asyncio
async def test_real_oversized_mandatory_group_is_pending_and_siblings_are_reviewed_without_clipping(monkeypatch):
    texts, _, wire, parsed, _ = layout_fixture(monkeypatch)
    originals, calls, saved = deepcopy(wire.references), [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(next(iter(payload['final_claims_and_gaps'])))
            return response(payload)

    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'), model_client=Model())
    result = await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 90, checkpoints=saved)
    assert calls == ['P0', 'P2', 'L0']
    assert result['pending_checks'] == [{'item': 'P1', 'reason': 'research_evidence_group_too_large'}]
    assert result['points_checked'] == 2 and result['status'] == 'partial'
    assert result['hints'] == [{'path': ['answer', 'points', 1],
        'review_signal': 'citation_layout', 'instruction': review.CITATION_LAYOUT}]
    assert fingerprint(parsed.mission_checkpoint.answer.points[1].model_dump()) not in result['positive_witnesses']
    assert not result['candidates'] and not saved.get('transient_assertions')
    assert wire.references == originals and len(wire.references[6]['quote']) > 24000
    await review.reasoned_review(service, wire, parsed.mission_checkpoint.answer, 90, checkpoints=saved)
    assert calls == ['P0', 'P2', 'L0'], 'Exact sibling checks remain reusable; no false packing proof is saved'


@pytest.mark.asyncio
@pytest.mark.parametrize('slots', [False, True])
@pytest.mark.parametrize('outcome', ['repaired', 'empty', 'packing_failure'])
async def test_layout_repair_preserves_statement_or_withholds_only_target_and_rechecks_subset(monkeypatch, slots, outcome):
    texts, work, wire, parsed, _ = layout_fixture(monkeypatch, slots=slots)
    before, coverage, calls, saved = deepcopy(parsed.mission_checkpoint.answer.model_dump()), [], [], {}
    audits(monkeypatch, texts[1], coverage)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            if 'final_claims_and_gaps' in payload:
                item = next(iter(payload['final_claims_and_gaps'].values()))
                calls.append(item.get('statement', item.get('gap')))
                assert 'prior_review_concerns' not in payload, 'A layout defect is not a semantic objection'
                return response(payload)
            correction = payload['correction_target']
            assert correction['edit_scope'] == 'citations' and correction['previous_statement'] == texts[1]
            assert all(review.citation_layout_issue(issue) for issue in correction['validation_errors'])
            assert 'statement' not in kwargs['response_schema']['properties']['points']['items']['properties']
            if outcome == 'empty':
                return json.dumps({'points': []})
            selected = next(p['citation_ref'] for s in payload['sources'] for p in s['passages']
                if p['text'] == wire.references[5]['quote'])
            return json.dumps({'points': [{'evidence': [{'citation_ref': selected, 'role': 'support'}]}]})

    if outcome == 'packing_failure':
        async def unavailable_writer(*args, **kwargs):
            assert kwargs['correction']['edit_scope'] == 'citations'
            raise DomainError('Synthetic correction packet too large', 422, 'research_evidence_group_too_large')
        monkeypatch.setattr(review, 'answer_request', unavailable_writer)
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'), model_client=Model())
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    answer = parsed.mission_checkpoint.answer
    expected = texts[:3] if outcome == 'repaired' else [texts[0], texts[2]]
    assert [p.statement for p in answer.points] == expected
    assert answer.points[0].model_dump() == before['points'][0] and answer.points[-1].model_dump() == before['points'][2]
    assert answer.limitations == [texts[3]] and result['factual_review']['pending_checks'] == []
    assert coverage[-1] == expected and calls.count(texts[0]) == calls.count(texts[2]) == 1
    assert calls.count(texts[1]) == (1 if outcome == 'repaired' else 0), 'Only a fitting corrected layout can be reviewed'
    if outcome == 'repaired':
        assert answer.points[1].evidence[0].quote == wire.references[5]['quote']
        assert result['rejected_points'] == []
    else:
        assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'research_evidence_group_too_large'}]
        assert result['question_coverage'] == 'missing' and result['rejected_points'] == [1]
    if slots:
        assert wire.point_requests == ['R0'] * len(expected) and wire.response_slots['R0']['remaining_gap'] == texts[3]


@pytest.mark.asyncio
async def test_real_prior_objection_survives_layout_repair_and_can_still_withhold_proposal(monkeypatch):
    texts, work, wire, parsed, _ = layout_fixture(monkeypatch)
    coverage, saved, calls = [], {}, []
    audits(monkeypatch, texts[1], coverage)
    prior = {'target': 'points', 'signal': 'not_established', 'instruction': 'The original requires the named custodian.',
        'original_refs': [4], 'reviewer_notes': [{'comment': 'Check the exact custodian qualification.', 'original_refs': [4]}]}
    identity = fingerprint({'request_key': None, 'point': parsed.mission_checkpoint.answer.points[1].model_dump()})
    saved['repair_concerns'] = {identity: review.carry_concerns({}, [texts[1]], [prior])}

    async def writer(service, current, *args, **kwargs):
        assert 'edit_scope' not in kwargs['correction'], 'An actual prior objection permits the existing factual correction'
        assert prior in kwargs['correction']['validation_errors'] and prior in kwargs['feedback']['issues']
        return [AssessmentPoint(statement=texts[1], evidence=[{**current.references[5], 'role': 'support'}])], '', {'status': 'proposed'}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            data = json.loads(response(payload))
            if item.get('statement') == texts[1]:
                issues = list(payload['prior_review_concerns']['concerns'].values())
                assert len(issues) == 1 and issues[0]['instruction'] == prior['instruction']
                assert issues[0]['original_refs'] == [4] and issues[0]['reviewer_notes'][0]['original_refs'] == [4]
                assert any(p.get('citation_ref') == 4 for s in payload['source_context'] for p in s['passages'])
                for concern in data['concern_checks']:
                    concern.update(outcome='cannot_assess', citation_refs=[])
                calls.append('unresolved-real-objection')
            return json.dumps(data)

    monkeypatch.setattr(review, 'answer_request', writer)
    result = await review.finalize(SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'), model_client=Model()),
        work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert calls == ['unresolved-real-objection']
    assert [p.statement for p in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'unresolved_concern'}]


@pytest.mark.asyncio
async def test_layout_then_provider_interruption_keeps_retry_gate_and_reuses_checked_siblings(monkeypatch):
    texts, work, wire, parsed, _ = layout_fixture(monkeypatch)
    original, saved, calls, coverage, resumed = deepcopy(parsed.mission_checkpoint.answer.model_dump()), {}, [], [], [False]
    audits(monkeypatch, texts[1], coverage)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if assertion == texts[2] and not resumed[0]:
                raise DomainError('Synthetic upstream timeout', 504, 'model_upstream_timeout')
            return response(payload)

    async def writer(*args, **kwargs):
        assert resumed[0], 'Pending provider work retains its ordinary native retry gate'
        return [], '', {'status': 'invalid_answer'}

    monkeypatch.setattr(review, 'answer_request', writer)
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'), model_client=Model())
    with pytest.raises(DomainError) as error:
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'model_upstream_timeout'
    assert parsed.mission_checkpoint.answer.model_dump() == original and 'final_correction_round' not in saved
    assert not saved.get('deferred_final_review'), 'No automatic checked-partial authorization was supplied'
    resumed[0] = True
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert calls.count(texts[0]) == calls.count(texts[3]) == 1
    assert calls.count(texts[2]) == 2 and texts[1] not in calls
    assert result['factual_review']['pending_checks'] == [] and coverage[-1] == [texts[0], texts[2]]


@pytest.mark.parametrize('augmentation', ['original_refs', 'original_text', 'reviewer_notes'])
def test_augmented_layout_marker_cannot_erase_real_originals(augmentation):
    _, _, wire, parsed = fixture()
    point = parsed.mission_checkpoint.answer.points[0]
    issue = {'target': 'points', 'signal': 'citation_layout', 'instruction': review.CITATION_LAYOUT}
    item = {'statement': point.statement, 'passages': [p.model_dump() for p in point.evidence]}
    _, previous, _, refs = review.review_projection(wire, item, {'previous_statements': [], 'issues': [issue]})
    assert previous is None and refs == [1]
    issue[augmentation] = {'original_refs': [2], 'original_text': [wire.references[2]['quote']],
        'reviewer_notes': [{'comment': 'A real qualification applies.', 'original_refs': [2]}]}[augmentation]
    _, previous, _, refs = review.review_projection(wire, item, {'previous_statements': [], 'issues': [issue]})
    assert not review.citation_layout_issue(issue) and previous['concerns'] and 2 in refs


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['source_access_changed', 'research_evidence_required_reference_invalid', 'model_upstream_timeout'])
async def test_other_selection_failures_still_propagate(monkeypatch, code):
    _, _, wire, parsed = fixture()

    async def fail(*args, **kwargs):
        raise DomainError('Synthetic selection failure', 422, code)

    monkeypatch.setattr(pack, 'select_evidence', fail)
    with pytest.raises(DomainError) as error:
        await review.reasoned_review(SimpleNamespace(settings=Settings(_env_file=None)), wire,
            parsed.mission_checkpoint.answer, 90)
    assert error.value.code == code


@pytest.mark.asyncio
async def test_fresh_fast_concern_and_exact_originals_survive_interrupted_layout_replacement(monkeypatch):
    # Keep this test on the owned request slot; flat late aggregate amendment
    # behavior is exercised separately from the interrupted layout correction.
    texts, work, wire, parsed, _ = layout_fixture(monkeypatch, slots=True)
    before, coverage, saved, resumed, writers = deepcopy(parsed.mission_checkpoint.answer.model_dump()), [], {}, [False], []
    audits(monkeypatch, texts[1], coverage)

    async def fast(settings, work, wire, answer, *args, **kwargs):
        return {'status': 'checked', 'hints': [] if resumed[0] else [
            {'path': ['answer', 'points', 1], 'review_signal': 'not_established'}], 'decisions': []}

    async def writer(service, current, *args, **kwargs):
        issues = kwargs['correction']['validation_errors']
        fresh = next(issue for issue in issues if issue['instruction'] == review.FAST_ADVISORY)
        assert fresh['original_text'] == [before['points'][1]['evidence'][0]['quote']]
        writers.append(deepcopy(issues))
        if not resumed[0]:
            raise DomainError('Synthetic interrupted correction', 504, 'model_upstream_timeout')
        return [AssessmentPoint(statement=texts[1], evidence=[{**current.references[5], 'role': 'support'}])], '', {'status': 'proposed'}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            assert next(iter(payload['final_claims_and_gaps'].values())).get('statement') != texts[1]
            return response(payload)

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(review, 'answer_request', writer)
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_provider='swisscom'), model_client=Model())
    with pytest.raises(DomainError) as error:
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'model_upstream_timeout' and parsed.mission_checkpoint.answer.model_dump() == before
    plan = saved['final_correction_round']
    assert plan['completed'] == 0 and plan['tasks'][0]['prior_concerns']['issues'][0]['instruction'] == review.FAST_ADVISORY
    saved, resumed[0] = json.loads(json.dumps(saved)), True
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert writers[0] == writers[1], 'Fresh concern stays bound even when a subsequent fast check changes'
    assert any(issue['original_text'] == [before['points'][1]['evidence'][0]['quote']]
        for value in saved['repair_concerns'].values() for issue in value['issues'])
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'research_evidence_group_too_large'}]
    assert result['question_coverage'] == 'missing' and coverage[-1] == [texts[0], texts[2]]
