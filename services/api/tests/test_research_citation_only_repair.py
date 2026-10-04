"""Citation defects cannot authorize replacing a finding's factual subject."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_answer_parts import answer_request
from helvetic_lens.research_answer_review import repair_points


def original_findings():
    refs = {
        1: {'source_id': 'a', 'locator': 'p1',
            'quote': 'The patent license ends if the recipient institutes patent litigation.'},
        2: {'source_id': 'a', 'locator': 'p2', 'quote': 'License version 2.0'},
    }
    statement = 'Under version 2.0, the patent license ends if the recipient institutes patent litigation.'
    answer = AssessmentOutcome(status='possible_answer', limitations=[], points=[
        {'statement': statement, 'evidence': [{**refs[1], 'role': 'support'}]},
        {'statement': 'The document states the license version.', 'evidence': [{**refs[2], 'role': 'support'}]},
    ])
    wire = SimpleNamespace(references=refs, input={'original_question': 'When do patent rights end?'})
    return wire, answer


@pytest.mark.asyncio
@pytest.mark.parametrize('inject_statement', [False, True])
async def test_initial_precision_repair_cannot_replace_subject(inject_statement):
    wire, answer = original_findings()
    before = answer.model_copy(deep=True)
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            assert payload['correction_target']['edit_scope'] == 'citations'
            assert payload['correction_target']['previous_statement'] == before.points[0].statement
            item = options['response_schema']['properties']['points']['items']
            assert set(item['properties']) == set(item['required']) == {'evidence'}
            point = {'evidence': [{'citation_ref': 1, 'role': 'support'},
                {'citation_ref': 2, 'role': 'context'}]}
            if inject_statement:
                point['statement'] = 'The source publishes the full license text.'
            return json.dumps({'points': [point]})

    receipts = await repair_points(SimpleNamespace(model_client=Model()), wire, answer, 60,
        selected_references=wire.references)
    assert len(calls) == 1
    assert answer.points[0].statement == before.points[0].statement
    assert answer.points[1] == before.points[1]
    if inject_statement:
        assert not receipts and answer == before
    else:
        assert receipts and answer.points[0].evidence[1].model_dump() == {**wire.references[2], 'role': 'context'}


@pytest.mark.asyncio
async def test_citation_repair_resume_revalidates_raw_draft_and_keeps_host_statement():
    wire, answer = original_findings()
    statement = answer.points[0].statement
    correction = {'previous_statement': statement, 'validation_errors': [], 'edit_scope': 'citations'}
    saved, calls = {}, []

    class Model:
        async def complete(self, system, text, **options):
            calls.append(json.loads(text))
            return json.dumps({'points': [{'evidence': [
                {'citation_ref': 1, 'role': 'support'}, {'citation_ref': 2, 'role': 'context'}]}]})

    service = SimpleNamespace(model_client=Model())

    async def run(state, seconds=60):
        return await answer_request(service, wire, wire.input['original_question'], seconds,
            correction=correction, checkpoints=state, preselected_references=wire.references)

    points, _, receipt = await run(saved)
    binding = receipt['input_fingerprint']
    assert points[0].statement == statement and len(calls) == 1
    persisted = json.loads(json.dumps(saved))
    assert persisted[binding]['draft'] == {'points': [{'evidence': [
        {'citation_ref': 1, 'role': 'support'}, {'citation_ref': 2, 'role': 'context'}]}]}
    # Even a modified private canonical proposal cannot override the host-owned
    # statement. The evidence-only raw draft remains the accepted wire contract.
    for value in persisted.values():
        if 'proposal' in value and 'statement' in value['proposal']:
            value['proposal']['statement'] = 'The source publishes the license.'
    resumed, _, _ = await run(persisted, 0)
    assert resumed == points and len(calls) == 1
    malformed = deepcopy(saved)
    malformed[binding]['draft']['points'][0]['statement'] = 'The source publishes the license.'
    rejected, _, rejected_receipt = await run(malformed, 0)
    assert not rejected and rejected_receipt['status'] == 'invalid_answer' and len(calls) == 1
    wire.references[2]['quote'] += ' This edition remains version 2.0.'
    changed, _, changed_receipt = await run(saved)
    assert changed[0].statement == statement and len(calls) == 2
    assert changed_receipt['input_fingerprint'] != binding
    assert changed[0].evidence[1].quote == wire.references[2]['quote']


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['supported', 'statement_injection', 'unsupported_precision'])
async def test_nested_numeric_repair_only_selects_citations(outcome):
    wire, answer = original_findings()
    statement = answer.points[0].statement
    if outcome == 'unsupported_precision':
        statement = statement.replace('2.0', '2099')
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            properties = options['response_schema']['properties']
            if 'citation_refs' in properties:
                return json.dumps({'citation_refs': {'S0': [1, 2]}})
            calls.append(payload)
            if 'points' in properties:
                return json.dumps({'points': [{'statement': statement,
                    'evidence': [{'citation_ref': 1, 'role': 'support'}]}], 'remaining_gap': ''})
            assert set(properties) == {'evidence'}
            assert payload['previous_proposal']['statement'] == statement
            data = {'evidence': [{'citation_ref': 1, 'role': 'support'},
                {'citation_ref': 2, 'role': 'context'}]}
            if outcome == 'statement_injection':
                data['statement'] = 'The source publishes the license.'
            return json.dumps(data)

    points, _, receipt = await answer_request(SimpleNamespace(model_client=Model()), wire,
        wire.input['original_question'], 60)
    assert len(calls) == 2
    if outcome == 'supported':
        assert points[0].statement == statement
        assert [ref.quote for ref in points[0].evidence] == [value['quote'] for value in wire.references.values()]
    else:
        assert not points
        assert receipt['status'] == ('invalid_answer' if outcome == 'statement_injection' else outcome)
