"""Bounded provider views retain exact originals and durable all-corpus selection."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import DomainError
from helvetic_lens.research_evidence_pack import (
    POLICY,
    bounded_schema,
    provider_input,
    provider_sources,
    request_characters,
    select_evidence,
)


def corpus(count=10, quote=None):
    references = {i: {'source_id': f's{i}', 'locator': 'p1',
        'quote': quote or f'Original {i}. ' + 'Station capacity context. ' * 60}
        for i in range(1, count + 1)}
    sources = [{'id': f's{i}', 'title': f'Original {i}', 'sha256': f'hash-{i}',
        'url': f'https://example.test/{i}', 'discovery_links': [{'url': 'https://example.test/next'}]}
        for i in range(1, count + 1)]
    point = {'type': 'object', 'properties': {
        'evidence': {'type': 'array', 'minItems': 1, 'items': {'type': 'object',
            'properties': {'citation_ref': {'type': 'integer', 'minimum': 1, 'maximum': count}},
            'required': ['citation_ref']}}, 'statement': {'type': 'string'}},
        'required': ['evidence', 'statement']}
    schema = {'type': 'object', 'properties': {
        'points': {'type': 'array', 'minItems': 1, 'items': point},
        'remaining_gaps': {'type': 'array', 'items': {'type': 'string'}}}}
    return SimpleNamespace(references=references,
        input={'original_question': 'Explain station capacity and its limits.', 'sources': sources},
        schema=schema, system='Write the answer using exact original references.')


class Selector:
    def __init__(self, choose):
        self.choose, self.calls = choose, []

    async def complete(self, system, text, **options):
        payload = json.loads(text)
        assert '"uniqueItems"' not in json.dumps(options['response_schema'])
        self.calls.append((system, payload, options))
        if payload['phase'] == 'consolidate':
            ranked = sorted(payload['groups'], key=lambda group: not any(
                self.choose(payload, None, key) for key in group['primary_refs']))
            return json.dumps({'assessment': 'Prioritize distinct original findings and their qualifications.',
                'ranked_groups': [group['id'] for group in ranked]})
        return json.dumps({'citation_refs': {source['selection_key']: [key
            for key in source['selectable_refs'] if self.choose(payload, source, key)]
            for source in payload['sources']}})


def service(model, allowance=9000):
    return SimpleNamespace(model_client=model, settings=SimpleNamespace(
        apertus_context_chars=allowance, apertus_model='fictional-model'))


@pytest.mark.asyncio
async def test_small_complete_pack_needs_no_selection_and_keeps_host_links():
    wire, model = corpus(2), Selector(lambda *_: True)
    original = deepcopy(wire.__dict__)
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60)
    assert result == wire.references and result is not wire.references and not model.calls
    assert wire.__dict__ == original
    assert all('discovery_links' not in item for item in provider_sources(wire, result))
    selected_schema = bounded_schema(wire.schema, {2: result[2]})
    assert selected_schema['properties']['points']['items']['properties']['evidence']['items']['properties']['citation_ref'] == {
        'type': 'integer', 'enum': [2]}


def test_provider_metadata_keeps_every_unfinished_warning_and_discovery_obligation():
    wire = corpus(2)
    clean = {'title': 'A completed original', 'url': 'https://example.test/complete',
        'read_complete': True, 'analysis_complete': True, 'unread_reason': None,
        'warnings': [], 'unresolved_references': []}
    outstanding = [{**clean, **change} for change in (
        {'read_complete': False}, {'analysis_complete': False}, {'unread_reason': 'OCR needed'},
        {'warnings': ['Table extraction was incomplete.']}, {'unresolved_references': ['Annex B']},
        {'error': 'A retained partial reader failure'})]
    wire.input['research_mission'] = {'question': wire.input['original_question'],
        'completion_policy': 'A host-enforced workflow policy.', 'documents': [clean, *outstanding],
        'unvalidated_proposals': [], 'attempted_queries': ['An earlier exact query'],
        'discovery_frontiers': [{'query': 'A pending query', 'more': True}]}
    original = deepcopy(wire.input)
    result = provider_input(wire, wire.references)
    mission = result['research_mission']
    assert mission['documents'] == outstanding
    assert mission['document_counts'] == {'total': 7, 'read_complete': 6, 'analysis_complete': 6}
    assert mission['attempted_queries'] == original['research_mission']['attempted_queries']
    assert mission['discovery_frontiers'] == original['research_mission']['discovery_frontiers']
    assert not {'question', 'completion_policy', 'unvalidated_proposals'} & mission.keys()
    assert wire.input == original
    assert list(result) == list(wire.input), 'The compact view preserves provider field order'
    mission['documents'][0]['warnings'].append('Provider-view-only change')
    assert wire.input == original, 'Compacting metadata must not share mutable host state'
    wire.input['research_mission'].update(question='A distinct earlier obligation.', unvalidated_proposals=['Unverified proposal'])
    different = provider_input(wire, {})['research_mission']
    assert different['question'] == 'A distinct earlier obligation.'
    assert different['unvalidated_proposals'] == ['Unverified proposal']


@pytest.mark.asyncio
async def test_completed_document_metadata_does_not_displace_a_whole_short_original():
    wire, model = corpus(1, 'An exact qualified observation. ' * 40), Selector(lambda *_: True)
    wire.references = {i: {'source_id': 's1', 'locator': f'p{i}',
        'quote': f'Exact context {i}. ' + 'Original qualification. ' * 15} for i in range(1, 15)}
    wire.input['research_mission'] = {'documents': [{'title': 'Completed title ' * 30,
        'read_complete': True, 'analysis_complete': True, 'warnings': [],
        'unresolved_references': [], 'unread_reason': None} for _ in range(30)]}
    assert request_characters(wire.system, {**wire.input, 'sources': provider_sources(wire, wire.references)},
        wire.schema) > 12000
    result = await select_evidence(service(model, 12000), wire, wire.input['original_question'], 60)
    assert result == wire.references and not model.calls
    assert len(wire.input['research_mission']['documents']) == 30


@pytest.mark.asyncio
async def test_every_source_is_considered_and_late_qualifier_survives_repetitive_early_sources():
    wire = corpus(12)
    wire.references[12]['quote'] = 'The reported capacity is conditional on the bypass remaining closed. ' * 18
    wire.references[13] = {'source_id': 's12', 'locator': 'p2',
        'quote': 'Exception: opening the bypass reduces usable output; no unconditional total is stated.'}
    model, checkpoints, progress = Selector(lambda _payload, _source, key: key in {1, 12}), {}, []
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, on_progress=lambda: progress.append(True))
    examined = [key for _, payload, _ in model.calls for source in payload['sources'] for key in source['selectable_refs']]
    assert set(examined) == set(wire.references) and len(examined) == len(wire.references)
    assert set(result) == {1, 12, 13} and result[13] == wire.references[13]
    assert len(model.calls) > 1 and len(progress) == len(model.calls)
    assert all(request_characters(system, payload, options['response_schema']) <= 9000
        for system, payload, options in model.calls)
    assert all(node['status'] == 'complete' and node['policy_fingerprint'] == POLICY
        for node in checkpoints['evidence_selection'].values())


@pytest.mark.asyncio
async def test_complete_paragraph_and_adjacent_qualification_are_not_sliced():
    wire = corpus(1)
    wire.references = {i: {'source_id': 's1', 'locator': f'p{i}' if i < 28 else 'p28',
        'quote': f'Exact window {i}. ' + 'Original context. ' * 24} for i in range(1, 31)}
    model = Selector(lambda _payload, _source, key: key == 29)
    result = await select_evidence(service(model), wire, 'Explain the qualification.', 60)
    assert set(result) == {27, 28, 29, 30}
    assert result == {key: wire.references[key] for key in result}
    assert set(key for _, payload, _ in model.calls for source in payload['sources']
        for key in source['selectable_refs']) == set(wire.references)
    for _, payload, _ in model.calls:
        assert len(payload['sources']) == 1
        passages = payload['sources'][0]['excerpts']
        assert len({passage['citation_ref'] for passage in passages}) == len(passages)


@pytest.mark.asyncio
async def test_completed_batches_resume_after_pause_without_repeating_provider_work():
    wire, checkpoints = corpus(), {}
    model = Selector(lambda _payload, _source, key: key == 10)
    def pause():
        raise RuntimeError('Native pause after persisted progress')
    with pytest.raises(RuntimeError, match='Native pause'):
        await select_evidence(service(model), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, on_progress=pause)
    assert len(checkpoints['evidence_selection']) == 1
    retained = json.loads(json.dumps(checkpoints))
    first_payload = model.calls[0][1]
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=retained)
    assert set(result) == {10}
    assert sum(payload == first_payload for _, payload, _ in model.calls) == 1
    count = len(model.calls)
    assert await select_evidence(service(model), wire, wire.input['original_question'], 0, checkpoints=retained) == result
    assert len(model.calls) == count


@pytest.mark.asyncio
async def test_duplicate_valid_routing_ids_are_normalized_without_replaying_prior_success():
    wire, checkpoints = corpus(), {}
    previous_model = Selector(lambda _payload, _source, key: key in {1, 10})
    def pause():
        raise RuntimeError('Pause after a valid unique selection was saved')
    with pytest.raises(RuntimeError, match='Pause'):
        await select_evidence(service(previous_model), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, on_progress=pause)
    retained = json.loads(json.dumps(checkpoints))
    prior_key, prior_receipt = next(iter(retained['evidence_selection'].items()))
    assert prior_receipt['selected'] == [1]

    class Repeated(Selector):
        async def complete(self, *args, **kwargs):
            result = json.loads(await super().complete(*args, **kwargs))
            # A repeated eligible ID carries no additional evidence and may
            # exceed maxItems even though the unique selection is in bounds.
            result['citation_refs'] = {key: values * 3 for key, values in result['citation_refs'].items()}
            return json.dumps(result)

    model = Repeated(lambda _payload, _source, key: key in {1, 10})
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=retained)
    assert result == {key: wire.references[key] for key in (1, 10)}
    assert retained['evidence_selection'][prior_key] == prior_receipt
    assert all(payload != previous_model.calls[0][1] for _, payload, _ in model.calls)
    assert all(len(node['selected']) == len(set(node['selected'])) for node in retained['evidence_selection'].values())
    count = len(model.calls)
    restored = json.loads(json.dumps(retained))
    assert await select_evidence(service(model), wire, wire.input['original_question'], 0, checkpoints=restored) == result
    assert len(model.calls) == count


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['question', 'quote', 'hash', 'model'])
async def test_cache_is_bound_to_exact_source_question_and_provider(changed):
    wire, checkpoints, model = corpus(), {}, Selector(lambda *_: False)
    current_service = service(model)
    question = wire.input['original_question']
    await select_evidence(current_service, wire, question, 60, checkpoints=checkpoints)
    original_count = len(model.calls)
    if changed == 'question':
        question = 'What constraint determines capacity?'
    elif changed == 'quote':
        wire.references[1]['quote'] += ' A newly captured qualification.'
    elif changed == 'hash':
        wire.input['sources'][0]['sha256'] = 'changed-capture'
    else:
        current_service.settings.apertus_model = 'different-model'
    await select_evidence(current_service, wire, question, 60, checkpoints=checkpoints)
    assert len(model.calls) > original_count


@pytest.mark.asyncio
async def test_consolidation_uses_only_retained_exact_originals():
    wire = corpus()
    model = Selector(lambda payload, _source, key: payload['phase'] == 'select' or key in {1, 10})
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60,
        request_size=lambda refs: 5500 + sum(len(ref['quote']) + 100 for ref in refs.values()))
    assert set(result) == {1, 10}
    assert {payload['phase'] for _, payload, _ in model.calls} == {'select', 'consolidate'}
    for _, payload, _ in model.calls:
        for source in payload['sources']:
            for passage in source['excerpts']:
                assert passage['text'] == wire.references[passage['citation_ref']]['quote']


@pytest.mark.asyncio
async def test_consolidation_costs_match_caller_and_survivors_compete_across_prior_batches():
    wire = corpus(40, 'Original capacity context and applicable conditions. ' * 15)
    wire.references[41] = {'source_id': 's40', 'locator': 'p2',
        'quote': 'This late exception limits the interpretation of the earlier measurement.'}
    question = 'Explain the capacity measurement and every condition on that interpretation.'
    wire.input['original_question'] = question
    # The downstream caller owns its actual envelope, including instructions
    # and schema absent from this selector's transport.
    def measured(references):
        return 5000 + sum(len(ref['quote']) + 350 for ref in references.values())

    class Consolidator(Selector):
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            self.calls.append((system, payload, options))
            if payload['phase'] == 'select':
                chosen = {key for source in payload['sources'] for key in source['selectable_refs']}
                assert 'consolidation_budget' not in payload, 'Previously accepted first-pass requests stay identical'
            else:
                for group in payload['groups']:
                    context = {key: wire.references[key] for key in group['retained_refs']}
                    assert group['additional_request_characters'] == measured(context) - measured({})
                    assert group['mandatory'] == bool({1, 40}.intersection(group['primary_refs']))
                return json.dumps({'assessment': 'The distinct finding and late qualification are indispensable.',
                    'ranked_groups': [group['id'] for group in payload['groups']]})
            return json.dumps({'citation_refs': {source['selection_key']: [key
                for key in source['selectable_refs'] if key in chosen] for source in payload['sources']}})

    model, checkpoints = Consolidator(None), {}
    result = await select_evidence(service(model), wire, question, 60, checkpoints=checkpoints,
        request_size=measured, required_refs=(1, 40))
    assert {1, 40, 41} <= set(result) and measured(result) <= 9000
    assert all(ref == wire.references[key] for key, ref in result.items())
    assert set(key for _, payload, _ in model.calls if payload['phase'] == 'select'
        for source in payload['sources'] for key in source['selectable_refs']) == set(wire.references)
    consolidation = [payload for _, payload, _ in model.calls if payload['phase'] == 'consolidate']
    prior_sources = []
    crossed = False
    for payload in consolidation:
        current = {source['id'] for source in payload['sources']}
        if sum(bool(current & earlier) for earlier in prior_sources) >= 2:
            crossed = True
        prior_sources.append(current)
    assert crossed, 'Another bounded level must compare survivors from different earlier partitions'
    assert all(request_characters(system, payload, options['response_schema']) <= 9000
        for system, payload, options in model.calls)
    assert len({node['policy_fingerprint'] for node in checkpoints['evidence_selection'].values()}) == 2
    count = len(model.calls)
    assert await select_evidence(service(model), wire, question, 0, checkpoints=json.loads(json.dumps(checkpoints)),
        request_size=measured, required_refs=(1, 40)) == result
    assert len(model.calls) == count


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['empty', 'foreign', 'boolean', 'string'])
async def test_invalid_ranking_retains_completed_selection_and_retries_only_unfinished_work(invalid):
    wire, checkpoints = corpus(), {}
    def measured(refs):
        return 5500 + sum(len(ref['quote']) + 100 for ref in refs.values())

    class Ranker(Selector):
        fail = True

        async def complete(self, *args, **kwargs):
            data = json.loads(await super().complete(*args, **kwargs))
            if 'ranked_groups' in data:
                ranking = data['ranked_groups']
                if self.fail:
                    data['ranked_groups'] = {'empty': [], 'foreign': [9999, *ranking],
                        'boolean': [True, *ranking], 'string': [str(ranking[0]), *ranking]}[invalid]
                else:
                    # Duplicate routing choices carry no additional priority.
                    data['ranked_groups'] = [ranking[0], *ranking]
            return json.dumps(data)

    model = Ranker(lambda payload, _source, key: payload['phase'] == 'select' or key in {1, 10})
    with pytest.raises(DomainError) as error:
        await select_evidence(service(model), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, request_size=measured)
    assert (error.value.status, error.value.code) == (503, 'research_evidence_pack_incomplete')
    assert checkpoints['evidence_selection']
    assert all(node['policy_fingerprint'] == POLICY for node in checkpoints['evidence_selection'].values())
    first_pass = [payload for _, payload, _ in model.calls if payload['phase'] == 'select']
    model.fail = False
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, request_size=measured)
    assert result == {key: wire.references[key] for key in (1, 10)}
    assert measured(result) <= 9000
    assert [payload for _, payload, _ in model.calls if payload['phase'] == 'select'] == first_pass
    count = len(model.calls)
    assert await select_evidence(service(model), wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(checkpoints)), request_size=measured) == result
    assert len(model.calls) == count


@pytest.mark.asyncio
async def test_partial_ranking_keeps_model_priority_and_appends_existing_groups_last():
    wire, checkpoints = corpus(4), {}

    class PartialRanker(Selector):
        async def complete(self, *args, **kwargs):
            data = json.loads(await super().complete(*args, **kwargs))
            if 'ranked_groups' in data:
                data['ranked_groups'] = [4, 4]
            return json.dumps(data)

    model = PartialRanker(lambda *_: True)
    result = await select_evidence(service(model, 24000), wire, wire.input['original_question'], 60,
        checkpoints=checkpoints, fits=lambda references: len(references) <= 2)
    assert result == {key: wire.references[key] for key in (1, 4)}
    repaired = [node for node in checkpoints['evidence_selection'].values() if node.get('unranked')]
    assert len(repaired) == 1 and repaired[0]['unranked'] == [1, 2, 3]
    assert repaired[0]['selected'] == [4, 1]
    count = len(model.calls)
    assert await select_evidence(service(model, 24000), wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(checkpoints)), fits=lambda references: len(references) <= 2) == result
    assert len(model.calls) == count


@pytest.mark.asyncio
async def test_nonshrinking_consolidation_has_explicit_failure_not_an_infinite_loop():
    wire, model, checkpoints = corpus(), Selector(lambda *_: True), {}
    with pytest.raises(DomainError) as error:
        await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert error.value.code == 'research_evidence_pack_no_progress'
    for phase in ('select', 'consolidate'):
        examined = [key for _, payload, _ in model.calls if payload['phase'] == phase
            for source in payload['sources'] for key in source['selectable_refs']]
        assert sorted(examined) == sorted(wire.references), 'A nonshrinking pass must stop without replaying groups'
    count = len(model.calls)
    with pytest.raises(DomainError, match='no progress'):
        await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert len(model.calls) == count


@pytest.mark.asyncio
async def test_indivisible_oversized_original_fails_before_any_partial_selection():
    wire, model = corpus(), Selector(lambda *_: False)
    wire.references[10]['quote'] = 'Entire indivisible original. ' * 1000
    with pytest.raises(DomainError) as error:
        await select_evidence(service(model), wire, wire.input['original_question'], 60)
    assert error.value.code == 'research_evidence_group_too_large' and not model.calls


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['foreign', 'missing', 'wrong_source', 'boolean', 'float', 'string'])
async def test_invalid_selection_is_not_cached_or_returned_as_partial(invalid):
    wire, checkpoints = corpus(), {}
    class Invalid:
        async def complete(self, _system, _text, **options):
            groups = options['response_schema']['properties']['citation_refs']['properties']
            chosen = {key: [] for key in groups}
            key = next(iter(groups))
            ref = groups[key]['items']['enum'][0]
            if invalid == 'missing':
                del chosen[key]
            else:
                other = next(name for name in groups if name != key)
                foreign_source = groups[other]['items']['enum'][0]
                chosen[key] = {'foreign': [9999], 'wrong_source': [foreign_source, foreign_source],
                    'boolean': [True], 'float': [float(ref)], 'string': [str(ref)]}[invalid]
            return json.dumps({'citation_refs': chosen})
    with pytest.raises(DomainError) as error:
        await select_evidence(service(Invalid()), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert error.value.code == 'research_evidence_selection_invalid'
    assert checkpoints == {'evidence_selection': {}}


@pytest.mark.asyncio
async def test_empty_selection_is_valid_complete_and_forbids_cited_output():
    wire, model, checkpoints = corpus(), Selector(lambda *_: False), {}
    wire.schema['properties']['directions'] = {'type': 'array', 'minItems': 1, 'items': {'type': 'object'}}
    assert await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=checkpoints) == {}
    assert all(node['selected'] == [] for node in checkpoints['evidence_selection'].values())
    empty_schema = bounded_schema(wire.schema, {})
    assert empty_schema['properties']['points']['maxItems'] == 0
    assert empty_schema['properties']['points']['minItems'] == 0
    assert empty_schema['properties']['directions']['minItems'] == 0
    assert empty_schema['properties']['directions']['maxItems'] == 0
    assert wire.schema['properties']['points']['minItems'] == 1


@pytest.mark.asyncio
async def test_expired_budget_preserves_completed_batches_but_is_not_complete(monkeypatch):
    from helvetic_lens import research_evidence_pack
    now, checkpoints, wire = [0.0], {}, corpus()
    monkeypatch.setattr(research_evidence_pack, 'monotonic', lambda: now[0])
    model = Selector(lambda *_: False)
    def elapsed():
        now[0] = 55.0
    with pytest.raises(DomainError) as error:
        await select_evidence(service(model), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, on_progress=elapsed)
    assert error.value.code == 'research_evidence_pack_incomplete' and error.value.status == 503
    assert len(model.calls) == len(checkpoints['evidence_selection']) == 1


@pytest.mark.asyncio
async def test_caller_fit_predicate_is_used_and_required_witnesses_survive_model_omission():
    wire, model = corpus(4), Selector(lambda *_: False)
    result = await select_evidence(service(model, 24000), wire, wire.input['original_question'], 60,
        fits=lambda references: len(references) <= 2, required_refs=(4,))
    assert set(result) == {4} and model.calls
    assert any(payload['required_refs'] == [4] for _, payload, _ in model.calls)


@pytest.mark.asyncio
async def test_combined_mandatory_context_cannot_be_dropped_to_fit():
    wire, model = corpus(4), Selector(lambda *_: False)
    with pytest.raises(DomainError) as error:
        await select_evidence(service(model, 24000), wire, wire.input['original_question'], 60,
            fits=lambda references: len(references) <= 1, required_refs=(1, 4))
    assert error.value.code == 'research_evidence_group_too_large' and not model.calls
