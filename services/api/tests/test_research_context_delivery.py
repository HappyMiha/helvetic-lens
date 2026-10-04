"""Initial writing and correction keep the same distant source qualifications."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_original_context import source, wire_for
from test_research_review_resilience import response

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_answer_parts import answer_request
from helvetic_lens.research_evidence_pack import provider_input
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_original_context import contextual_references


@pytest.mark.asyncio
@pytest.mark.parametrize('correction', [False, True])
async def test_initial_pack_and_targeted_writer_keep_literal_conditions_after_local_remapping(correction):
    observation = 'The archive may distribute the material under the following rules.'
    condition = 'Distribution is permitted only after written approval.'
    period = 'The assessment concerns observations made in the year 2022.'
    original = source('report', [
        ('page-2-text-1', observation), ('page-9-text-1', condition), ('page-12-text-1', period)])

    def binding(index):
        excerpt = original['excerpts'][index]
        return {'source_id': original['id'], 'sha256': original['sha256'],
            'locator': excerpt['passage'], 'quote': excerpt['text']}

    original['source_context'] = [{'observation': binding(0), 'anchors': [
        {'kind': 'condition', **binding(1)}, {'kind': 'time', **binding(2)}]}]
    unrelated = source('other', [('page-1-text-1', 'The unrelated registry describes its administrative office.')],
        sha='b' * 64, url='https://example.test/other.pdf')
    wire = wire_for([unrelated, original])
    before = deepcopy(wire.__dict__)
    primary = next(key for key, ref in wire.references.items() if ref['quote'] == observation)
    retained = contextual_references(wire, [primary])
    initial = provider_input(wire, retained)

    def assert_context(groups, field):
        passages = [entry for group in groups for entry in group[field]]
        supplied = {entry['citation_ref']: entry for entry in passages if 'citation_ref' in entry}
        main = next(entry for entry in supplied.values() if entry['text'] == observation)
        linked = {anchor['kind']: [supplied[key]['text'] for key in anchor['citation_refs']]
            for anchor in main['context_anchors']}
        assert linked == {'condition': [condition], 'time': [period]}
        assert all(text != unrelated['excerpts'][0]['text'] for text in
            [entry['text'] for entry in passages])
        return supplied

    initial_refs = assert_context(initial['sources'], 'excerpts')
    assert min(initial_refs) > 1, 'Initial evidence retains canonical citation identities'
    calls = []
    statement = 'Distribution requires written approval; the assessment concerns the year 2022.'

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            props = options['response_schema']['properties']
            if 'citation_refs' in props:
                assert not correction
                calls.append('select')
                return json.dumps({'citation_refs': {key: [primary] if primary in spec['items']['enum'] else []
                    for key, spec in props['citation_refs']['properties'].items()}})
            calls.append('write')
            supplied = assert_context(payload['sources'], 'passages')
            assert list(supplied) == [1, 2, 3], 'Local writing IDs are not the initial canonical IDs'
            return json.dumps({'points': [{'statement': statement, 'evidence': [
                {'citation_ref': key, 'role': 'support'} for key in supplied]}],
                **({'remaining_gap': ''} if not correction else {})})

    options = {'correction': {'previous_statement': 'The archive can always distribute the material.',
        'validation_errors': []}, 'preselected_references': {primary: wire.references[primary]}} if correction else {}
    points, gap, receipt = await answer_request(SimpleNamespace(model_client=Model()), wire,
        'Under which conditions may the archive distribute the material, and what period is covered?', 60, **options)
    assert receipt['status'] == 'proposed' and gap == ''
    assert [point.statement for point in points] == [statement]
    assert [ref.quote for ref in points[0].evidence] == [observation, condition, period]
    assert all(ref.source_id == 'report' for ref in points[0].evidence)
    assert calls == (['write'] if correction else ['select', 'write'])
    assert wire.__dict__ == before


@pytest.mark.asyncio
async def test_rewritten_point_retains_earlier_witness_conditions_without_promoting_them_to_support():
    old = source('earlier', [
        ('page-2-text-1', 'The archive may distribute the material.'),
        ('page-9-text-1', 'Distribution requires written permission from the owner.')])
    old['source_context'] = [{'observation': {
        'source_id': old['id'], 'sha256': old['sha256'],
        'locator': old['excerpts'][0]['passage'], 'quote': old['excerpts'][0]['text']},
        'anchors': [{'kind': 'condition', 'source_id': old['id'], 'sha256': old['sha256'],
            'locator': old['excerpts'][1]['passage'], 'quote': old['excerpts'][1]['text']}]}]
    revised = source('later', [('page-1-text-1', 'The archive received written permission from the owner.')],
        sha='b' * 64, url='https://example.test/permission.pdf')
    wire = wire_for([old, revised])
    primary, anchor, support = list(wire.references)
    answer = AssessmentOutcome(status='partial', points=[{
        'statement': revised['excerpts'][0]['text'],
        'evidence': [{**wire.references[support], 'role': 'support'}]}], limitations=[])
    concerns = {'P0': {'previous_statements': ['The archive may always distribute the material.'],
        'issues': [{'reason': 'The earlier assertion omitted required permission.', 'original_refs': [primary]}],
        'context_refs': [primary]}}
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            passages = {entry['citation_ref']: entry for group in payload['source_context']
                for entry in group['passages'] if 'citation_ref' in entry}
            assert set(passages) == {primary, anchor, support}
            assert passages[primary]['context_anchors'] == [
                {'kind': 'condition', 'citation_refs': [anchor]}]
            assert passages[anchor]['text'] == old['excerpts'][1]['text']
            assert payload['selected_citation_refs'] == [support]
            return response(payload)

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, concerns=concerns)
    assert result['pending_checks'] == [] and len(calls) == 1
    assert answer.points[0].evidence[0].source_id == revised['id']
    assert len(answer.points[0].evidence) == 1
