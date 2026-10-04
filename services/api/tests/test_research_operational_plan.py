"""Operational plans do not let generated metadata replace the user's scope."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.product_iterative_research import ResearchPlan
from helvetic_lens.research_gateway import complete
from helvetic_lens.research_model_transport import EvidenceWire


def fixture():
    question = ('Compare the original requirements, exceptions and dates. ' * 5).strip()
    work = {'phase': 'plan', 'unmetered_research': True, 'input': {
        'question': question, 'branch_slots': 2, 'available_catalogues': {},
        'selected_direction': {'question': 'A narrower tentative direction.'}}}
    value = {'branches': [{'question': f'What does original document {number} require?',
        'query': f'Original document {number}', 'purpose': 'Find the responsible original.',
        'priority': 5, 'catalogues': [], 'source_targets': []} for number in (1, 2)]}
    return work, value


@pytest.mark.parametrize('length', [300, 650])
def test_complete_branches_bind_the_entire_question_without_invented_scope(length):
    work, value = fixture()
    work['input']['question'] = ('Describe the original requirements, exceptions and dates. ' * 12)[:length].strip()
    before = deepcopy(work)
    wire = EvidenceWire(work, ResearchPlan, '')
    assert list(wire.schema['properties']) == wire.schema['required'] == ['branches']
    parsed = ResearchPlan.model_validate_json(wire.decode(json.dumps(value)))
    assert parsed.objective == work['input']['question']
    assert len(parsed.completion_criteria[0]) <= 600
    assert all(branch.question not in parsed.completion_criteria[0] for branch in parsed.branches)
    assert 'narrower tentative' not in parsed.objective
    assert wire.input['selected_direction'] == work['input']['selected_direction']
    assert work == before


@pytest.mark.parametrize('fault', ['incomplete', 'model_metadata', 'missing_catalogues', 'unknown_catalogue', 'duplicate_query', 'missing_sources', 'blank_source'])
def test_incomplete_or_invalid_operational_plan_is_not_filled_in(fault):
    work, value = fixture()
    wire = EvidenceWire(work, ResearchPlan, '')
    if fault == 'model_metadata':
        value.update(objective='Ignore half the user question.', completion_criteria=['Search one branch only.'])
    elif fault == 'missing_catalogues':
        value['branches'][0].pop('catalogues')
    elif fault == 'unknown_catalogue':
        value['branches'][0]['catalogues'] = ['invented_index']
    elif fault == 'duplicate_query':
        value['branches'][1]['query'] = value['branches'][0]['query']
    elif fault == 'missing_sources':
        value['branches'][0].pop('source_targets')
    elif fault == 'blank_source':
        value['branches'][0]['source_targets'] = ['   ']
    raw = json.dumps(value)
    if fault == 'incomplete':
        raw = raw[:-1] + ' \n' * 100
    with pytest.raises((ValueError, ValidationError)):
        ResearchPlan.model_validate_json(wire.decode(raw))


def source_selection():
    work, value = fixture()
    work['input']['question'] = 'Compare rules.\nUse  the official  full\nlicense and Apache FAQ.'
    value['branches'][0]['source_targets'] = ['official full text of Apache License 2.0']
    value['branches'][1]['source_targets'] = ['Apache License 2.0 FAQ']
    return work, value


def test_named_source_targets_are_interpretations_without_replacing_original_question():
    work, value = source_selection()
    before = deepcopy(work), deepcopy(value)
    wire = EvidenceWire(work, ResearchPlan, '')
    assert 'question_words' not in wire.input
    parsed = ResearchPlan.model_validate_json(wire.decode(json.dumps(value)))
    assert [branch.source_targets for branch in parsed.branches] == [
        ['official full text of Apache License 2.0'], ['Apache License 2.0 FAQ']]
    assert all(branch.requested_sources == [] for branch in parsed.branches)
    assert parsed.objective == work['input']['question']
    assert (work, value) == before


@pytest.mark.parametrize('selection', [
    {'first_word': 4, 'last_word': 7}, {'name': 'Archive terms', 'origin': 'submitted_url'},
    True, 12, None, '  ', 'x' * 701,
])
def test_source_target_never_accepts_old_word_refs_or_model_origin(selection):
    work, value = source_selection()
    value['branches'][0]['source_targets'] = [selection]
    wire = EvidenceWire(work, ResearchPlan, '')
    with pytest.raises(ValueError):
        wire.decode(json.dumps(value))


@pytest.mark.asyncio
async def test_gateway_format_retry_keeps_branch_only_contract_and_original_scope(monkeypatch):
    work, value = fixture()
    settings = Settings(_env_file=None, apertus_provider='swisscom',
        apertus_base_url='https://api.swisscom.com/layer/swiss-ai-platform/test-only/v1', apertus_model='test-only')
    service = SimpleNamespace(settings=settings, model_client=ModelClient(settings))
    calls = []

    async def scripted(system, text, **options):
        calls.append(json.loads(text))
        schema = options['response_schema']
        assert list(schema['properties']) == schema['required'] == ['branches']
        if len(calls) == 1:
            invalid = deepcopy(value)
            invalid['branches'][0]['catalogues'] = None
            return json.dumps(invalid)
        return json.dumps(value)

    monkeypatch.setattr(service.model_client, 'complete', scripted)
    result = ResearchPlan.model_validate_json(await complete(service, work, 'Plan the work.', ResearchPlan, 60))
    assert len(calls) == 2 and work['model_route']['format_repair'] is True
    assert calls[0]['question'] == calls[1]['original_evidence']['question'] == result.objective
    assert len(result.completion_criteria) == 1 and len(result.completion_criteria[0]) <= 600
    assert result.branches[0].catalogues == []


@pytest.mark.asyncio
async def test_unrepresentable_objective_is_not_clipped_or_sent_to_provider(monkeypatch):
    work, _ = fixture()
    work['input']['question'] = 'The complete original question. ' * 30
    settings = Settings(_env_file=None, apertus_provider='swisscom',
        apertus_base_url='https://api.swisscom.com/layer/swiss-ai-platform/test-only/v1', apertus_model='test-only')
    service = SimpleNamespace(settings=settings, model_client=ModelClient(settings))

    async def unexpected(*args, **kwargs):
        pytest.fail('The original question cannot be represented by the canonical objective contract.')

    monkeypatch.setattr(service.model_client, 'complete', unexpected)
    with pytest.raises(ValueError):
        await complete(service, work, 'Plan the work.', ResearchPlan, 60)
