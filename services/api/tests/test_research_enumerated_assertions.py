"""Explicit compound lists need every item's evidence without another review."""
import json
from types import SimpleNamespace

import pytest
from test_research_clause_witnesses import fixture, response

from helvetic_lens.config import Settings
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_review_witnesses import assertion_clauses

STATEMENT = ('Within the recorded survey period, the results include: '
    '(a) a coastal increase, (b) an inland decrease, and (c) unchanged mountain measurements.')


@pytest.mark.asyncio
@pytest.mark.parametrize('judgment', ['missing', 'negative', 'supported'])
async def test_a_whole_sentence_approval_cannot_hide_a_missing_or_negative_list_item(judgment):
    wire, answer = fixture(statement=STATEMENT)
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            assert payload['assertion_clauses']['S0'] == STATEMENT
            assert payload['final_claims_and_gaps']['P0']['statement'] == STATEMENT
            clauses = payload['assertion_clauses']
            assert len(clauses) == 4 and all(value in STATEMENT for value in clauses.values())
            value = response(payload, wire.references)
            if judgment == 'missing':
                del value['clauses']['S0.item2']
            elif judgment == 'negative':
                value['clauses']['S0.item2']['verdict'] = 'not_established'
            return json.dumps(value)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert len(calls) == 1 and answer.points[0].statement == STATEMENT
    if judgment == 'supported':
        assert result['status'] == 'checked' and result['positive_witnesses'] and not result['hints']
    else:
        assert not result['positive_witnesses'] and not result['candidates']
        if judgment == 'missing':
            assert result['pending_checks'] == [{'item': 'P0', 'reason': 'invalid_response'}]
            assert not any(key.startswith('clauses:') for key in cache)
        else:
            assert result['hints'][0]['review_signal'] == 'not_established'
        assert result['status'] == ('partial' if judgment == 'missing' else 'checked')


@pytest.mark.parametrize('text', [
    'The rule in section (a) applies alongside section (b).',
    'Observations include coastal, inland, and mountain locations.',
    'Results: (a) coastal gains, (c) inland losses.',
    'Results: (1) coastal gains, (3) inland losses.',
    'Results: (a) , (b) inland losses.',
])
def test_parentheticals_and_unordered_or_empty_fragments_do_not_create_new_assertions(text):
    assert assertion_clauses(text) == {'S0': text}


def test_many_numbered_items_preserve_exact_shared_scope_and_complete_tail_in_existing_envelope():
    text = 'Only during the earlier period, observations include:\n' + ';\n'.join(
        f'({index}) recorded comparison {index}' for index in range(1, 13)) + '.'
    clauses = assertion_clauses(text)
    assert len(clauses) == 8 and clauses['S0'] == text
    items = [value for key, value in clauses.items() if '.item' in key]
    assert ''.join(items) == text[text.index('(1)'):]
    assert items[-1].endswith('(12) recorded comparison 12.')


@pytest.mark.asyncio
@pytest.mark.parametrize('negative_item', [False, True])
async def test_citation_rebinding_retains_whole_sentences_without_duplicating_or_detaching_items(negative_item):
    sibling = 'Another independent observation remains.'
    wire, answer = fixture(statement=STATEMENT + ' ' + sibling)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            value = response(payload, wire.references, cited=2)
            if negative_item:
                value['clauses']['S0.item2']['verdict'] = 'not_established'
            return json.dumps(value)

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60)
    assert result['candidates']['P0']['statement'] == (sibling if negative_item else STATEMENT + ' ' + sibling)
    assert all(ref['quote'] == wire.references[2]['quote'] for ref in result['candidates']['P0']['evidence'])
