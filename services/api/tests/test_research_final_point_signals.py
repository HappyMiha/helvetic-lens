"""Fast review is advisory; only original-bound resolution controls delivery."""
import json
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_final_review import finalize


@pytest.mark.asyncio
@pytest.mark.parametrize('fast_choice', ['supported', 'not_established', 'contradicted', 'unavailable'])
async def test_final_fast_objection_can_be_dismissed_by_originals_without_rewriting(monkeypatch, fast_choice):
    source = {'source_id': 'original', 'locator': 'p1', 'quote': 'The observatory started operations in 2041.'}
    statement = 'The observatory began operating in 2041.'
    answer = AssessmentOutcome(status='possible_answer', points=[{
        'statement': statement, 'evidence': [{**source, 'role': 'support'}]}], limitations=[])
    work = {'input': {'original_question': 'When did the observatory open?',
        'sources': [{'id': 'original', 'kind': 'public_source', 'title': 'Observatory record'}]}}
    wire = SimpleNamespace(input=work['input'], references={1: source}, point_requests=[], request_keys={}, response_slots={})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    calls = []

    class Engine:
        model, url = 'synthetic-decision', 'https://example.test/decision'

        async def choose(self, state, instructions, criteria):
            if 'statement' in state:
                assert state == {'statement': statement, 'passages': [source['quote']]}
                if fast_choice == 'unavailable':
                    raise DecisionUnavailable('timeout')
                choice = fast_choice
            else:
                choice = 'covered'
            return Decision('jev', self.model, choice, {choice: 1}, 1, 1, 1, 1, 1)

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            assert 'final_claims_and_gaps' in payload, 'A valid sibling must not be rewritten'
            judgment = {'verdict': 'supported', 'reason': 'The original establishes the same opening year.', 'citation_refs': [1]}
            response = {'overall': judgment, 'clauses': {'S0': judgment}}
            concerns = payload.get('prior_review_concerns', {}).get('concerns', {})
            assert bool(concerns) == (fast_choice in {'not_established', 'contradicted'})
            if concerns:
                issue = next(iter(concerns.values()))
                assert issue['original_refs'] == [1] and 'original_text' not in issue
                assert payload['source_context'][0]['passages'][0]['text'] == source['quote']
                assert 'advisory' in issue['instruction']
                response['concern_checks'] = [{'id': key, 'outcome': 'resolved',
                    'reason': 'The supported paraphrase preserves the original meaning.', 'citation_refs': [1]} for key in concerns]
            return json.dumps(response)

    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await finalize(service, work, wire, parsed, 90, checkpoints={}, defer_pending=True)
    assert [point.statement for point in answer.points] == [statement]
    assert answer.limitations == [] and answer.status == 'possible_answer'
    assert len(calls) == 1
    assert not result['hints']
    assert result['fast_point_review']['status'] == ('partial' if fast_choice == 'unavailable' else 'checked')
