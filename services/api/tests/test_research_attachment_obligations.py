"""Mechanical attachments never become a second factual-review obligation."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_clause_witnesses import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import Settings


def attachment(wire, *, signal='citation_attachment'):
    return {'target': 'points', 'signal': signal, 'instruction': review.CITATION_ATTACHMENT,
        'original_refs': [2]}


@pytest.mark.asyncio
@pytest.mark.parametrize('signal', ['citation_attachment', 'not_established'])
async def test_current_witness_still_requires_attachment_without_reassessing_old_host_instruction(signal):
    wire, answer = fixture(statement='The inland zone measurement fell.')
    calls = []

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            assert 'prior_review_concerns' not in payload
            assert any(p.get('citation_ref') == 2 for s in payload['source_context'] for p in s['passages'])
            return json.dumps(response(payload, wire.references, cited=2))

    previous = {'P0': {'previous_statements': [answer.points[0].statement],
        'issues': [attachment(wire, signal=signal)]}}
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await review.reasoned_review(service, wire, answer, 60, concerns=previous)
    assert result['pending_checks'] == [] and result['status'] == 'checked'
    assert result['hints'][0]['review_signal'] == 'citation_attachment'
    assert result['hints'][0]['candidate_windows'] == [{'text': wire.references[2]['quote']}]
    assert result['candidates']['P0']['evidence'] == [{**wire.references[2], 'role': 'support'}]
    assert answer.points[0].evidence[0].quote == wire.references[1]['quote'], 'No silent approval or attachment'
    answer.points[0].evidence = [type(answer.points[0].evidence[0])(**wire.references[2], role='support')]
    completed = await review.reasoned_review(service, wire, answer, 60, concerns=previous)
    assert completed['hints'] == [] and completed['positive_witnesses']
    assert len(calls) == 2, 'Changed citations receive the existing factual check'


@pytest.mark.asyncio
@pytest.mark.parametrize('other', ['fast', 'factual_note', 'unknown_signal'])
async def test_attachment_separation_does_not_erase_semantic_uncertainty(other):
    wire, answer = fixture(statement='The inland zone measurement fell.', cited=2)
    host = attachment(wire)
    if other == 'fast':
        issue = {'target': 'points', 'signal': 'fast_not_established',
            'instruction': review.FAST_ADVISORY, 'original_refs': [2]}
    elif other == 'factual_note':
        issue = {**host, 'reviewer_notes': [{'comment': 'The original scope does not match.', 'original_refs': [1]}]}
    else:
        issue = {**host, 'signal': 'unrecognized_semantic_objection'}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            assert len(payload['prior_review_concerns']['concerns']) == 1
            data = response(payload, wire.references, cited=2)
            for concern in data['concern_checks']:
                concern.update(outcome='cannot_assess', citation_refs=[], reason='Resolved in prose only.')
            return json.dumps(data)

    result = await review.reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, concerns={'P0': {'previous_statements': [], 'issues': [host, issue]}})
    assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
    assert not result['positive_witnesses'] and not result['candidates']


def test_host_attachment_still_rejects_unbound_originals_before_projection():
    wire, answer = fixture()
    issue = {**attachment(wire), 'original_refs': [999]}
    item = {'statement': answer.points[0].statement, 'passages': [r.model_dump() for r in answer.points[0].evidence]}
    with pytest.raises(ValueError, match='Unbound review original'):
        review.review_projection(wire, item, {'previous_statements': [], 'issues': [issue]})


@pytest.mark.asyncio
async def test_full_finalizer_repairs_only_citations_then_checks_unchanged_assertion(monkeypatch):
    wire, answer = fixture(statement='The inland zone measurement fell.')
    wire.request_keys, wire.point_requests, wire.response_slots = {}, [], {}
    work = {'input': {**wire.input, 'sources': [{'id': 'report', 'kind': 'public_source'}]}}
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    initial, calls, saved = deepcopy(answer.model_dump()), [], {}

    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            if 'final_claims_and_gaps' in payload:
                assert 'prior_review_concerns' not in payload
                return json.dumps(response(payload, wire.references, cited=2))
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return json.dumps({'citation_refs': {s['selection_key']: [2] for s in payload['sources']}})
            assert payload['correction_target']['edit_scope'] == 'citations'
            point_schema = kwargs['response_schema']['properties']['points']['items']
            assert 'statement' not in point_schema['properties'], 'Attachment cannot buy a factual rewrite'
            chosen = next(p['citation_ref'] for s in payload['sources'] for p in s['passages']
                if p['text'] == wire.references[2]['quote'])
            return json.dumps({'points': [{'evidence': [{'citation_ref': chosen, 'role': 'support'}]}]})

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', coverage)
    result = await review.finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert [p.statement for p in answer.points] == [p['statement'] for p in initial['points']]
    assert answer.points[0].evidence[0].quote == wire.references[2]['quote']
    assert result['factual_review']['pending_checks'] == [] and result['rejected_points'] == []
    assert len([p for p in calls if 'final_claims_and_gaps' in p]) == 2
    assert answer.limitations == []
