"""A point retains every exact witness; representation does not approve truth."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import product_exploration as exploration
from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as final
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import Decision
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request, requested_schema
from helvetic_lens.research_gateway import answer_quantity_errors
from helvetic_lens.research_model_transport import EvidenceWire, shape_errors


def fixture(count=18):
    source = {'id': 'archive', 'kind': 'public_source', 'sha256': 'a' * 64,
        'title': 'Fictional archive conditions', 'url': 'https://example.test/conditions', 'excerpts': [
            {'passage': f'page-1-text-{i}-char-1',
             'text': f'Original clause {chr(64+i)} retains the permission and its exact governing qualification.'}
            for i in range(1, count+1)]}
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'What access and reproduction does this archive permit?',
        'research_mission': {}, 'sources': [source]}}
    schema = mission_schema(exploration.Briefing)
    return EvidenceWire(work, schema, ''), schema


@pytest.mark.parametrize('count', [1, 9, 16])
def test_point_canonical_wire_and_checkpoint_preserve_all_current_witnesses(count):
    wire, schema = fixture(count)
    point = {'statement': 'The archive permits consultation subject to the stated conditions.',
        'evidence': [{'citation_ref': key, 'role': 'support' if key % 2 else 'context'} for key in wire.references]}
    raw = {'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [point]}, 'next_action': 'finish'}
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    restored = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed)))
    assert restored.mission_checkpoint.answer == parsed.mission_checkpoint.answer
    assert [ref.model_dump() for ref in restored.mission_checkpoint.answer.points[0].evidence] == [
        {**wire.references[key], 'role': item['role']} for key, item in zip(wire.references, point['evidence'])]
    _, writer = requested_schema(wire.references, 1)
    assert not shape_errors({'points': [point], 'remaining_gap': ''}, writer, {})
    for evidence in ([], [{'citation_ref': 999, 'role': 'support'}]):
        invalid = {'points': [{**point, 'evidence': evidence}], 'remaining_gap': ''}
        assert shape_errors(invalid, writer, {}), 'Nonempty current witnesses remain mandatory'


@pytest.mark.asyncio
@pytest.mark.parametrize('next_result', ['contradicted', 'oversized'])
async def test_large_supported_union_is_an_exact_candidate_with_concerns_and_requires_next_review(monkeypatch, next_result):
    wire, _ = fixture()
    text = 'The archive permits consultation. The archive permits reproduction. The archive retains item restrictions.'
    answer = exploration.AssessmentOutcome(status='possible_answer', limitations=[], points=[
        {'statement': text, 'evidence': [{**wire.references[1], 'role': 'support'}]}])
    concern = {'previous_statements': ['Earlier wording omitted a condition.'],
        'issues': [{'instruction': 'Check the earlier restriction objection.', 'original_refs': [17]}]}
    calls = []

    async def rank(*args, **kwargs):
        return {'rankings': [{'query': text, 'references': list(wire.references),
            'scores': {key: 1 for key in wire.references}}], 'coverage': {'method': 'scripted'}}

    class Model:
        async def complete(self, system, serialized, **options):
            payload = json.loads(serialized)
            calls.append(payload)
            passages = {p['citation_ref']: p for source in payload['source_context'] for p in source['passages']
                if 'citation_ref' in p}
            assert set(passages) == set(wire.references), 'All complete original context is retained'
            assert payload['prior_review_concerns']['concerns']['C0']['original_refs'] == [17]
            verdict = 'supported' if len(calls) == 1 else 'contradicted'
            witnesses = [list(range(1, 7)), list(range(7, 13)), list(range(13, 17))]
            return json.dumps({'overall': {'verdict': verdict, 'reason': 'The exact original clauses govern.'},
                'clauses': {key: {'verdict': verdict, 'reason': 'The exact original clauses govern.',
                    'witnesses': [{'key': passages[ref]['witness_key'], 'scope_relation': 'compatible'}
                        for ref in (witnesses[index] if len(calls) == 1 else [17])]}
                    for index, key in enumerate(payload['assertion_clauses'])},
                'concern_checks': [{'id': 'C0', 'outcome': 'resolved' if len(calls) == 1 else 'remains',
                    'reason': 'The original restriction was considered.', 'citation_refs': [17]}]})

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    first = await final.reasoned_review(service, wire, answer, 60, concerns={'P0': concern})
    candidate = first['candidates']['P0']
    assert candidate['statement'] == text
    assert candidate['evidence'] == [{**wire.references[key], 'role': 'support'} for key in range(1, 17)]
    assert set(candidate['context_refs']) == set(range(1, 18)), 'Keep supporting and earlier objection witnesses'
    assert first['hints'][0]['review_signal'] == 'citation_attachment', 'First review has not approved the new attachment'
    answer.points[0] = exploration.AssessmentPoint(statement=candidate['statement'], evidence=candidate['evidence'])
    inherited = {**deepcopy(concern), 'context_refs': candidate['context_refs']}
    if next_result == 'oversized':
        wire.references[18]['quote'] *= 500
        wire.input['sources'][0]['excerpts'][17]['text'] = wire.references[18]['quote']
    second = await final.reasoned_review(service, wire, answer, 60, concerns={'P0': inherited})
    assert not second['positive_witnesses'] and not second['candidates']
    if next_result == 'contradicted':
        assert len(calls) == 2
        assert calls[1]['selected_citation_refs'] == list(range(1, 17))
        assert second['hints'][0]['review_signal'] == 'contradicted'
    else:
        assert len(calls) == 1, 'Mandatory oversized context is never clipped or sent'
        assert second['points_checked'] == 0
        assert second['pending_checks'] == [{'item': 'P0', 'reason': 'research_evidence_group_too_large'}]


@pytest.mark.asyncio
async def test_nested_precision_completion_can_retain_ninth_context_without_changing_statement():
    wire, _ = fixture(9)
    wire.references[9]['quote'] = 'Archive decision dated 2042.'
    wire.input['sources'][0]['excerpts'][8]['text'] = wire.references[9]['quote']
    statement = 'The archive adopted the consultation conditions in 2042.'
    evidence = [{'citation_ref': key, 'role': 'support'} for key in range(1, 9)]
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            calls.append(value)
            if 'points' in options['response_schema']['properties']:
                return json.dumps({'points': [{'evidence': evidence}]})
            assert set(options['response_schema']['properties']) == {'evidence'}
            return json.dumps({'evidence': evidence})

    result, _, receipt = await answer_request(SimpleNamespace(model_client=Model()), wire,
        wire.input['original_question'], 60, correction={'edit_scope': 'citations',
            'previous_statement': statement, 'validation_errors': []}, preselected_references=wire.references)
    assert len(calls) == 2 and receipt['status'] == 'proposed'
    assert result[0].statement == statement
    assert len(result[0].evidence) == 9 and result[0].evidence[-1].role == 'context'
    assert result[0].evidence[-1].quote == wire.references[9]['quote']
    assert not answer_quantity_errors(exploration.AssessmentOutcome(status='partial', points=result, limitations=[]))


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict', ['supported', 'contradicted'])
async def test_companion_precision_context_still_requires_ordinary_entailment_after_eight_witnesses(monkeypatch, verdict):
    wire, _ = fixture(9)
    wire.references[9]['quote'] = 'Archive decision dated 2042.'
    statement = 'The archive adopted the consultation conditions in 2042.'
    answer = exploration.AssessmentOutcome(status='partial', limitations=[], points=[{'statement': statement,
        'evidence': [{**wire.references[key], 'role': 'support'} for key in range(1, 9)]}])
    calls = []

    class Engine:
        async def choose(self, state, *args):
            calls.append(state)
            assert len(state['passages']) == 9 and state['statement'] == statement
            return Decision('jev', 'test', verdict, {verdict: 1}, 1, 1, 1, 1, 1)

    monkeypatch.setattr(audit.decision, 'engines', lambda settings: {'jev': Engine()})
    receipts = await audit.complete_citation_context(Settings(_env_file=None), wire.work, wire, answer, 60)
    assert len(calls) == 1 and answer.points[0].statement == statement
    assert len(answer.points[0].evidence) == (9 if verdict == 'supported' else 8)
    assert bool(receipts[0]['added_context']) == (verdict == 'supported')


@pytest.mark.asyncio
async def test_large_citation_only_writer_grammar_changes_binding_without_accepting_old_invalid_proposal(monkeypatch):
    from helvetic_lens import research_answer_parts as parts

    wire, _ = fixture(16)
    wire.work.update(run_id='current-run', generation=1)
    statement = 'The archive permits consultation under the retained conditions.'
    calls, saved = [], {}
    current_schema = parts.requested_schema

    def previous_schema(*args, **kwargs):
        point, schema = current_schema(*args, **kwargs)
        point['properties']['evidence']['maxItems'] = 8
        schema['properties']['points']['items']['properties']['evidence']['maxItems'] = 8
        return point, schema

    class Model:
        async def complete(self, system, text, **options):
            calls.append(options['response_schema'])
            return json.dumps({'points': [{'evidence': [{'citation_ref': key, 'role': 'support'}
                for key in range(1, 17)]}]})

    service = SimpleNamespace(model_client=Model())
    correction = {'edit_scope': 'citations', 'previous_statement': statement, 'validation_errors': []}
    monkeypatch.setattr(parts, 'requested_schema', previous_schema)
    rejected, _, old = await parts.answer_request(service, wire, wire.input['original_question'], 60,
        correction=correction, preselected_references=wire.references, checkpoints=saved)
    assert rejected == [] and old['status'] == 'invalid_answer'
    monkeypatch.setattr(parts, 'requested_schema', current_schema)
    accepted, _, new = await parts.answer_request(service, wire, wire.input['original_question'], 60,
        correction=correction, preselected_references=wire.references, checkpoints=json.loads(json.dumps(saved)))
    assert new['input_fingerprint'] != old['input_fingerprint']
    assert len(accepted[0].evidence) == 16 and accepted[0].statement == statement
    assert len(calls) == 2
    assert 'maxItems' not in calls[-1]['properties']['points']['items']['properties']['evidence']
