"""Rejected private work survives native redelivery without becoming approval."""
import json
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import DomainError
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request
from helvetic_lens.research_answer_review import repair_points
from helvetic_lens.research_gateway import answer_quantity_errors
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import completed_work, made_progress


def wire_for(*, generation=1, year=2001):
    return EvidenceWire({'run_id': 'current-investigation', 'generation': generation, 'phase': 'brief',
        'unmetered_research': True, 'input': {'original_question': 'When were the records published?',
            'research_mission': {}, 'sources': [{'id': 'original', 'kind': 'public_source',
                'title': 'Publication registry', 'excerpts': [
                    {'passage': f'p{i}', 'text': f'Record {i} was published in {value}.'}
                    for i, value in enumerate((year, 2002, 2003), 1)]}]}}, mission_schema(Briefing), '')


def evidence(ref):
    return [{'citation_ref': ref, 'role': 'support'}]


def selected(options):
    groups = options['response_schema']['properties']['citation_refs']['properties']
    return json.dumps({'citation_refs': {key: value['items']['enum'] for key, value in groups.items()}})


@pytest.mark.asyncio
async def test_rejected_precision_task_is_not_rebought_after_sibling_rate_limit():
    wire = wire_for()
    answer = AssessmentOutcome(status='partial', limitations=[], points=[
        {'statement': f'Record {i} was published in {year}.',
            'evidence': [{**wire.references[1], 'role': 'support'}]}
        for i, year in enumerate((2099, 2002, 2003), 1)])
    saved, calls = {}, Counter()

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            if 'citation_refs' in options['response_schema']['properties']:
                calls['selection'] += 1
                return selected(options)
            if 'previous_proposal' in payload:
                calls['nested_rejected'] += 1
                return json.dumps({'evidence': evidence(1)})
            statement = payload['correction_target']['previous_statement']
            number = int(statement.split()[1])
            calls[number] += 1
            if number == 3 and calls[number] == 1:
                raise DomainError('Synthetic sibling outage', 503, 'model_rate_limited')
            return json.dumps({'points': [{'evidence': evidence(number)}]})

    service = SimpleNamespace(model_client=Model())
    with pytest.raises(DomainError, match='Synthetic sibling outage'):
        await repair_points(service, wire, answer, 60, checkpoints=saved)
    assert calls == Counter({'selection': 3, 1: 1, 2: 1, 3: 1, 'nested_rejected': 1})
    retained = json.loads(json.dumps(saved))
    progress = completed_work({'parts': retained})
    rejected = next(value for value in retained.values() if 'rejected_attempt' in value)
    assert 'draft' in rejected and 'proposal' not in rejected
    rejected_before = deepcopy(rejected)
    # Native source/attempt reconstruction plus actual JSON checkpoint roundtrip.
    resumed_wire = wire_for()
    resumed_answer = AssessmentOutcome.model_validate_json(answer.model_dump_json())
    await repair_points(service, resumed_wire, resumed_answer, 60, checkpoints=retained)
    assert calls == Counter({'selection': 3, 1: 1, 2: 1, 3: 2, 'nested_rejected': 1})
    assert next(value for value in retained.values() if 'rejected_attempt' in value) == rejected_before
    assert resumed_answer.points[0] == answer.points[0]
    assert [error['path'][2] for error in answer_quantity_errors(resumed_answer)] == [0]
    assert resumed_answer.points[1].evidence[0].quote == wire.references[2]['quote']
    assert resumed_answer.points[2].evidence[0].quote == wire.references[3]['quote']
    assert made_progress(progress, completed_work({'parts': retained}))  # Only the newly completed sibling.
    stable = completed_work({'parts': retained})
    await repair_points(service, resumed_wire, resumed_answer, 60, checkpoints=retained)
    assert not made_progress(stable, completed_work({'parts': retained}))
    assert calls[1] == calls['nested_rejected'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('new_input', ['explicit_generation', 'changed_original'])
async def test_new_attempt_or_changed_original_can_retry_without_losing_valid_sibling(new_input):
    wire = wire_for()
    saved, calls, retry = {}, Counter(), [False]
    rejected_target = {'previous_statement': 'Record 1 was published in 2099.',
        'validation_errors': [], 'edit_scope': 'citations'}
    sibling_target = {'previous_statement': 'Record 2 was published in 2002.',
        'validation_errors': [], 'edit_scope': 'citations'}

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            if 'previous_proposal' in payload:
                calls['nested'] += 1
                # A new explicit attempt may obtain a different response, but
                # cannot invent support for the unchanged 2099 assertion.
                return json.dumps({'evidence': [] if retry[0] else evidence(1)})
            number = int(payload['correction_target']['previous_statement'].split()[1])
            calls[number] += 1
            return json.dumps({'points': [{'evidence': evidence(number)}]})

    async def request(current_wire, target):
        return await answer_request(SimpleNamespace(model_client=Model()), current_wire,
            current_wire.input['original_question'], 60, checkpoints=saved,
            correction=target, preselected_references=current_wire.references)

    valid, _, valid_receipt = await request(wire, sibling_target)
    rejected, gap, receipt = await request(wire, rejected_target)
    assert valid and not rejected and gap == '' and receipt['status'] == 'unsupported_precision'
    saved = json.loads(json.dumps(saved))
    before = deepcopy(saved)
    retry[0] = True
    await request(wire_for(), rejected_target)
    assert saved == before and calls == Counter({1: 1, 2: 1, 'nested': 1})

    changed = wire_for(generation=2) if new_input == 'explicit_generation' else wire_for(year=2099)
    result, gap, next_receipt = await request(changed, rejected_target)
    assert calls[1] == 2
    assert gap == ''
    if new_input == 'explicit_generation':
        assert not result and next_receipt['status'] == 'unsupported_precision' and calls['nested'] == 2
        assert next_receipt['input_fingerprint'] == receipt['input_fingerprint']
        # A retained valid task still validates and returns without new calls.
        sibling, _, repeated = await request(changed, sibling_target)
        assert sibling == valid and repeated['input_fingerprint'] == valid_receipt['input_fingerprint']
        assert calls[2] == 1
    else:
        assert result[0].statement == rejected_target['previous_statement']
        assert result[0].evidence[0].quote == 'Record 1 was published in 2099.'
        assert next_receipt['input_fingerprint'] != receipt['input_fingerprint']
        assert calls['nested'] == 1
