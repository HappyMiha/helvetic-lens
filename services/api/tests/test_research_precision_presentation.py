"""Presentation labels do not bypass ordinary factual review or numeric grounding."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_final_coverage as coverage
from helvetic_lens import research_final_review as final
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema


def answer(statement, quote):
    return AssessmentOutcome(status='possible_answer', limitations=[], points=[{
        'statement': statement, 'evidence': [{'source_id': 'record', 'locator': 'p1',
            'quote': quote, 'role': 'support'}]}])


def test_consecutive_inline_markers_are_presentation_without_mutating_assertion_or_evidence():
    statement = ('The procedure requires: (1) include protocol version 2.0, (2) retain the dated record, '
        '(3) mark changes to the procedure, and (4) include the annex when applicable.')
    value = answer(statement, 'Protocol version 2.0 requires its text, a dated record, change notices and any applicable annex.')
    before = deepcopy(value.model_dump())
    assert not gateway.answer_quantity_errors(value)
    assert value.model_dump() == before
    assert gateway.numeric_tokens(statement) == {'1', '2', '3', '4', '2.0'}, 'Generic extraction tokens are unchanged'


@pytest.mark.parametrize('fact,token', [
    ('retain 1 record', '1'),
    ('use 25 mg', '25'),
    ('apply a 5% reduction', '5'),
    ('record the observation on 2024-05-12', '2024'),
    ('follow section 7.2', '7.2'),
    ('cite case 2024/183', '183'),
])
def test_numbers_within_items_still_need_original_grounding(fact, token):
    value = answer(f'The procedure requires: (1) {fact}; (2) retain the signed record.',
        'The procedure requires a signed record and the specified operating conditions.')
    errors = gateway.answer_quantity_errors(value)
    assert len(errors) == 1 and token in errors[0]['reason'].split(': ', 1)[1].split('. Cite', 1)[0].split(', ')
    value.points[0].evidence[0].quote += ' In particular, ' + fact + '.'
    assert not gateway.answer_quantity_errors(value)


@pytest.mark.parametrize('statement', [
    'The record names section (1).',
    'Sections (1) and (2) apply to the retained record.',
    'The record requires: (1) retain the original, (3) sign the copy.',
    '(1) Retain the original, (2) sign the copy.',
    'The cited sections are: (1), (2), and (3).',
    'The reported amounts are: (1.5) units, (2.5) units.',
])
def test_ambiguous_or_nonlist_parenthetical_numbers_remain_checked(statement):
    assert gateway.answer_quantity_errors(answer(statement, 'Retain the original record and sign the copy.'))


def test_source_list_markers_cannot_ground_a_factual_quantity():
    assert gateway.answer_quantity_errors(answer('The record requires 4 samples.',
        'The procedure requires: (1) label the sample, (2) seal it, (3) retain the record, and (4) sign the copy.'))


@pytest.mark.asyncio
async def test_gateway_sends_unchanged_list_to_factual_review_without_precision_repair(monkeypatch):
    # Scripted rejection proves routing only, not the semantic ability of a reviewer.
    statement = 'The protocol requires: (1) retain every record, and (2) always publish the signed annex.'
    quote = 'Retain the applicable records. Publish the signed annex only when the stated condition applies.'
    sibling = 'The protocol was issued by the archive.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'What does the archive protocol require?', 'research_mission': {},
        'sources': [{'id': 'record', 'kind': 'public_source', 'title': 'Archive protocol',
            'url': 'https://example.test/protocol', 'sha256': 'a' * 64,
            'excerpts': [{'passage': 'p1', 'text': quote}, {'passage': 'p2', 'text': sibling}]}]}}
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    reviewed, calls = [], []

    async def complete(*args, **kwargs):
        calls.append('writer')
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [{'statement': statement, 'evidence': [{'citation_ref': 1, 'role': 'support'}]},
                {'statement': sibling, 'evidence': [{'citation_ref': 2, 'role': 'support'}]}]},
            'next_action': 'finish'})

    async def no_original(*args, **kwargs):
        return None

    async def forbidden_repair(*args, **kwargs):
        pytest.fail('Presentation labels must not buy a citation-only repair')

    async def reject_unsupported_scope(service, work, wire, parsed, seconds, **kwargs):
        value = parsed.mission_checkpoint.answer
        reviewed.append(deepcopy(value.model_dump()))
        assert value.points[0].statement == statement and value.points[0].evidence[0].quote == quote
        value.points = value.points[1:]
        wire.point_requests = wire.point_requests[1:]
        value.status = 'partial'
        return {'hints': [], 'question_coverage': 'missing',
            'factual_review': {'status': 'checked', 'pending_checks': []}}

    async def missing(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'missing', 'removed_notices': 0, 'decisions': []}

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'original_check', no_original)
    monkeypatch.setattr(review, 'repair_points', forbidden_repair)
    monkeypatch.setattr(final, 'finalize', reject_unsupported_scope)
    monkeypatch.setattr(coverage, 'reconcile', missing)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    assert len(reviewed) == 1 and calls == ['writer']
    assert [point.statement for point in result.mission_checkpoint.answer.points] == [sibling]
    assert result.mission_checkpoint.answer.status == 'partial'
