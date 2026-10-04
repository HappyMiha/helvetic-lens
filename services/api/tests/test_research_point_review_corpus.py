"""A draft's citations cannot hide other retained originals from its reviewer."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_evidence_pack import request_characters


def corpus():
    sources, references = [], {}
    for source_id, texts in (
        ('summary', ['The permit ordinarily remains in effect.', 'This summary is subject to the operative terms.']),
        ('earlier', ['The earlier review identified a termination condition.', 'The condition concerns surrender by the permit operator.']),
        ('operative', ['The permit terminates when its operator surrenders it.', 'The termination applies only to that surrendered permit.']),
        ('unrelated', ['An unrelated administrative inventory. ' * 1000]),
    ):
        excerpts = []
        for index, text in enumerate(texts, 1):
            locator = f'page-1-text-{index}-char-1'
            references[len(references) + 1] = {'source_id': source_id, 'locator': locator, 'quote': text}
            excerpts.append({'passage': locator, 'text': text})
        sources.append({'id': source_id, 'sha256': source_id[0] * 64,
            'title': source_id, 'url': f'https://example.test/{source_id}', 'excerpts': excerpts})
    wire = SimpleNamespace(input={'original_question': 'What rights does the permit give me, and when do they end?',
        'sources': sources}, references=references, work={})
    answer = AssessmentOutcome(status='possible_answer', points=[{
        'statement': 'The permit cannot terminate.',
        'evidence': [{**references[1], 'role': 'support'}]}], limitations=[])
    concerns = {'P0': {'previous_statements': ['The permit remains effective indefinitely.'],
        'issues': [{'instruction': 'Check the earlier termination objection.', 'original_refs': [3]}]}}
    return wire, answer, concerns


def scripted_model(calls):
    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append((system, payload, options['response_schema']))
            passages = {p['citation_ref']: p for s in payload['source_context']
                for p in s['passages'] if 'citation_ref' in p}
            # A scripted negative judgment tests transport and repair propagation,
            # not the semantic accuracy of a real model.
            return json.dumps({'clauses': {key: {'verdict': 'contradicted', 'reason': 'The operative condition applies.',
                'witnesses': [{'key': passages[5]['witness_key'], 'scope_relation': 'compatible'}]}
                for key in payload['assertion_clauses']},
                'overall': {'verdict': 'contradicted', 'reason': 'The operative condition applies.'},
                'concern_checks': [{'id': key, 'outcome': 'remains', 'citation_refs': [5],
                    'reason': 'The operative condition applies.'} for key in payload['prior_review_concerns']['concerns']]})
    return Model()


@pytest.mark.asyncio
async def test_actual_selector_adds_uncited_original_and_keeps_mandatory_context_with_exact_cache(monkeypatch):
    wire, answer, concerns = corpus()
    before = deepcopy(wire.__dict__), answer.model_dump(), deepcopy(concerns)
    calls, rankings, checkpoints = [], [], {}
    settings = Settings(_env_file=None, apertus_provider='swisscom', apertus_context_chars=14000)

    async def rank(service, current, task, seconds, **options):
        assert current.references == wire.references, 'The selector must see the full authorized corpus'
        queries = retrieval._queries(current, task)
        assert queries[0] == answer.points[0].statement
        assert wire.input['original_question'] in queries
        rankings.append(queries)
        return {'rankings': [{'query': query, 'references': [5, 6, 1, 2, 3, 4, 7],
            'scores': {ref: 1 if ref == 5 else 0 for ref in current.references}} for query in queries],
            'coverage': {'method': 'scripted_ranking', 'semantic_status': 'not_evaluated'}}

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    service = SimpleNamespace(settings=settings, model_client=scripted_model(calls))

    async def run():
        return await final.reasoned_review(service, wire, answer, 60, checkpoints=checkpoints, concerns=concerns)

    result = await run()
    assert result['status'] == 'checked' and result['hints'][0]['review_signal'] == 'contradicted'
    system, payload, schema = calls[0]
    delivered = {p['citation_ref']: p['text'] for s in payload['source_context']
        for p in s['passages'] if 'citation_ref' in p}
    assert set(delivered) == {1, 2, 3, 4, 5, 6}
    assert delivered == {ref: wire.references[ref]['quote'] for ref in delivered}
    assert payload['selected_citation_refs'] == [1], 'Retrieved context is not silently promoted to a selected citation'
    assert request_characters(system, payload, schema, provider=settings.apertus_provider) <= settings.apertus_context_chars
    local_payload = {**payload, 'source_context': final.review_source_groups(wire,
        {key: value for key, value in wire.references.items() if key <= 4})}
    local_schema = final.scoped_review_schema(wire, answer.points[0].statement,
        {key: value for key, value in wire.references.items() if key <= 4}, {'C0': {}}, point=True)
    assert request_characters(system, local_payload, local_schema, provider=settings.apertus_provider) <= settings.apertus_context_chars
    assert len(rankings) == len(calls) == 1, 'A fitting citation-local view must still enter full-corpus selection'
    assert await run() == result
    assert len(rankings) == len(calls) == 1, 'Exact selection and successful review are reusable'
    assert (wire.__dict__, answer.model_dump(), concerns) == before

    # This original still does not fit the packet. Changing it nevertheless
    # invalidates the corpus-bound approval rather than reusing a narrower proof.
    wire.references[7]['quote'] += ' A newly captured inventory entry.'
    wire.input['sources'][-1]['excerpts'][0]['text'] = wire.references[7]['quote']
    wire.input['sources'][-1]['sha256'] = 'b' * 64
    await run()
    assert len(rankings) == len(calls) == 2
    assert calls[0] == calls[1], 'The renewed approval is required even when the selected packet happens to match'
    monkeypatch.setattr(final, 'POLICY', 'changed-review-policy')
    await run()
    assert len(rankings) == 2 and len(calls) == 3


@pytest.mark.asyncio
async def test_mandatory_cited_and_prior_context_cannot_be_dropped_to_fit(monkeypatch):
    wire, answer, concerns = corpus()
    wire.references[4]['quote'] *= 1000
    wire.input['sources'][1]['excerpts'][1]['text'] = wire.references[4]['quote']
    before = deepcopy(wire.__dict__)

    async def no_rank(*args, **kwargs):
        pytest.fail('The complete mandatory context must be checked before ranking optional evidence')

    monkeypatch.setattr(retrieval, 'rank_evidence', no_rank)
    calls = []
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_context_chars=14000), model_client=scripted_model(calls))
    result = await final.reasoned_review(service, wire, answer, 60, concerns=concerns)
    assert result['pending_checks'] == [{'item': 'P0', 'reason': 'research_evidence_group_too_large'}]
    assert result['hints'][0]['review_signal'] == 'citation_layout'
    assert result['points_checked'] == 0 and not result['positive_witnesses']
    assert not calls and wire.__dict__ == before


@pytest.mark.asyncio
async def test_mandatory_adjacent_context_is_closed_once_not_promoted_to_new_primary_seeds(monkeypatch):
    wire, answer, _ = corpus()
    refs = {key: {'source_id': 'paragraphs', 'locator': f'p{key}',
        'quote': f'Original paragraph {key} explains the retained permit.'} for key in range(1, 6)}
    refs[6] = wire.references[7]
    wire.references = refs
    wire.input['sources'] = [{'id': 'paragraphs', 'sha256': 'a' * 64, 'url': 'https://example.test/paragraphs',
        'excerpts': [{'passage': ref['locator'], 'text': ref['quote']} for ref in list(refs.values())[:5]]},
        wire.input['sources'][-1]]
    answer = AssessmentOutcome(status='possible_answer', points=[{
        'statement': answer.points[0].statement, 'evidence': [{**refs[3], 'role': 'support'}]}], limitations=[])

    class Captured(Exception):
        pass

    async def rank(*args, **kwargs):
        return {'rankings': [], 'coverage': {'method': 'scripted_no_optional_rank', 'semantic_status': 'not_evaluated'}}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            supplied = {p['citation_ref'] for source in payload['source_context'] for p in source['passages']}
            assert supplied == {2, 3, 4}, 'Adjacent context is retained once; its neighbors are not new mandatory seeds'
            raise Captured

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    service = SimpleNamespace(settings=Settings(_env_file=None, apertus_context_chars=14000), model_client=Model())
    with pytest.raises(Captured):
        await final.reasoned_review(service, wire, answer, 60)


@pytest.mark.asyncio
async def test_cached_point_review_still_checks_current_source_access(monkeypatch):
    wire, answer, concerns = corpus()
    wire.references.pop(7)
    wire.input['sources'].pop()
    calls, checkpoints, access_checks = [], {}, []
    withdrawn = False

    async def current(service, current_wire):
        access_checks.append(set(current_wire.references))
        if withdrawn:
            raise DomainError('Original access changed.', 409, 'research_evidence_scope_invalid')

    monkeypatch.setattr(retrieval, 'ensure_current', current)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=scripted_model(calls))
    await final.reasoned_review(service, wire, answer, 60, concerns=concerns, checkpoints=checkpoints)
    saved = deepcopy(checkpoints)
    withdrawn = True
    with pytest.raises(DomainError) as caught:
        await final.reasoned_review(service, wire, answer, 60, concerns=concerns, checkpoints=checkpoints)
    assert caught.value.code == 'research_evidence_scope_invalid'
    assert access_checks == [set(wire.references), set(wire.references)]
    assert len(calls) == 1 and checkpoints == saved


@pytest.mark.asyncio
async def test_fitting_gap_keeps_existing_full_corpus_path(monkeypatch):
    from helvetic_lens import research_evidence_pack as packing

    wire, _, _ = corpus()
    wire.references.pop(7)
    wire.input['sources'].pop()
    answer = AssessmentOutcome(status='partial', points=[], limitations=['The termination condition remains unknown.'])

    class Captured(Exception):
        pass

    async def no_selection(*args, **kwargs):
        pytest.fail('A fitting gap already supplies the full corpus without selection')

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            assert {p['citation_ref'] for s in payload['sources'] for p in s['passages']} == set(wire.references)
            assert payload['delivered_points'] == []
            raise Captured

    monkeypatch.setattr(packing, 'select_evidence', no_selection)
    with pytest.raises(Captured):
        await final.reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
