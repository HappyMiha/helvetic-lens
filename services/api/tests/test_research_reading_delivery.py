"""Source-scoped reading reaches real writer adapters without becoming evidence."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request, source_groups
from helvetic_lens.research_evidence_pack import provider_sources
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_reading_context import CONTRACT


def reading_wire(interpretation='The report describes preliminary local observations.'):
    question = 'What does the station report establish?'
    source_id, run_id = 'a' * 36, 'r' * 36
    text = 'The station records observations of its local surroundings.'
    qualification = 'These observations are preliminary and apply only to this station.'
    note = {'interpretation': interpretation,
        'role': 'context', 'level': 'document',
        'original': {'source_id': source_id, 'sha256': 'f' * 64, 'locator': 'p1', 'quote': text},
        'anchors': [{'kind': 'scope', 'source_id': source_id, 'sha256': 'f' * 64,
            'locator': 'p2', 'quote': qualification}]}
    source = {'id': source_id, 'sha256': 'f' * 64, 'kind': 'public_source',
        'url': 'https://example.test/station', 'title': 'Station report',
        'excerpts': [{'passage': 'p1', 'text': text}, {'passage': 'p2', 'text': qualification}],
        'reading_context': {'contract': CONTRACT, 'question': question,
            'investigation_id': run_id, 'notes': [note]}}
    work = {'phase': 'brief', 'run_id': run_id, 'input': {'original_question': question,
        'research_mission': {}, 'sources': [
            {'id': 'b' * 36, 'sha256': 'e' * 64, 'kind': 'public_source',
                'url': 'https://example.test/index', 'title': 'Unrelated index',
                'excerpts': [{'passage': 'other', 'text': 'A separate index records historical publications.'}]},
            source]}}
    return EvidenceWire(work, mission_schema(Briefing), ''), note


@pytest.mark.asyncio
async def test_bound_reading_reaches_initial_and_reindexed_writer_then_resumes_without_new_call():
    wire, original_note = reading_wire()
    before = deepcopy(wire.references)
    originals = {key: value for key, value in wire.references.items() if value['source_id'] == 'a' * 36}
    main = provider_sources(wire, originals)[0]
    note = main['reading_notes'][0]
    assert set(note) == {'level', 'original_citation_refs', 'context_anchors'}
    assert original_note['interpretation'] not in json.dumps(main)
    assert note['original_citation_refs'] == [2]
    assert note['context_anchors'][0]['citation_refs'] == [3]
    assert 'reading_notes' not in provider_sources(wire, {1: wire.references[1]})[0]
    assert all(original_note['interpretation'] != ref['quote'] for ref in wire.references.values())
    with pytest.raises(ValueError, match='missing a bound original anchor'):
        source_groups(wire, {2: wire.references[2]})
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            group = payload['sources'][0]
            local_note = group['reading_notes'][0]
            assert local_note['original_citation_refs'] == [1]
            assert local_note['context_anchors'][0]['citation_refs'] == [2]
            assert local_note['level'] == 'document' and 'role' not in local_note
            assert original_note['interpretation'] not in text
            assert 'pointers' in group['reading_scope'].lower() and 'scope' not in local_note
            assert [p['text'] for p in group['passages']] == [ref['quote'] for ref in originals.values()]
            return json.dumps({'points': [{'statement': 'The observations are local and preliminary.',
                'evidence': [{'citation_ref': 1, 'role': 'support'}, {'citation_ref': 2, 'role': 'context'}]}]})

    service, saved = SimpleNamespace(model_client=Model()), {}
    options = {'correction': {'previous_statement': 'The report describes all stations.', 'validation_errors': []},
        'preselected_references': originals}
    points, gap, receipt = await answer_request(service, wire, wire.input['original_question'], 60,
        checkpoints=saved, **options)
    assert receipt['status'] == 'proposed' and not gap and len(points) == 1
    assert [ref.quote for ref in points[0].evidence] == [ref['quote'] for ref in originals.values()]
    resumed, _, _ = await answer_request(service, wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(saved)), **options)
    assert resumed == points and len(calls) == 1
    assert wire.references == before
    changed, _ = reading_wire('The same report limits its observations to this station.')
    _, _, current_receipt = await answer_request(service, changed, changed.input['original_question'], 60,
        checkpoints=json.loads(json.dumps(saved)), **options)
    assert len(calls) == 1 and current_receipt['input_fingerprint'] == receipt['input_fingerprint']


@pytest.mark.asyncio
async def test_final_review_keeps_reading_context_and_does_not_reuse_a_changed_interpretation(monkeypatch):
    from test_research_review_resilience import response

    from helvetic_lens import research_answer_review as advisory
    from helvetic_lens import research_final_coverage as coverage
    from helvetic_lens import research_final_review as review
    from helvetic_lens.config import Settings

    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            station = next(group for group in payload['source_context'] if group['url'] == 'https://example.test/station')
            assert station['reading_notes'][0]['original_citation_refs'] == [2]
            assert all('interpretation' not in note and 'role' not in note for note in station['reading_notes'])
            return response(payload)

    async def checked(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered', 'decisions': []}

    async def covered(settings, work, wire, answer, requests, seconds, **kwargs):
        return [{'user_request': request, 'choice': 'covered', 'point_ids': ['P0']} for request in requests]

    monkeypatch.setattr(advisory, 'audit_points', checked)
    monkeypatch.setattr(advisory, 'audit', checked)
    monkeypatch.setattr(coverage, 'assess_requests', covered)
    settings = Settings(_env_file=None)
    service = SimpleNamespace(settings=settings, model_client=Model())
    cache = {}

    async def finish(wire):
        raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [{'statement': 'The observations are local and preliminary.',
                'evidence': [{'citation_ref': 2, 'role': 'support'}, {'citation_ref': 3, 'role': 'context'}]}]},
            'next_action': 'finish'})
        parsed = mission_schema(Briefing).model_validate_json(wire.decode(raw))
        result = await review.finalize(service, wire.work, wire, parsed, 60, checkpoints=cache)
        assert result['status'] == 'checked'
        assert parsed.mission_checkpoint.answer.points[0].evidence[0].quote == wire.references[2]['quote']

    first, _ = reading_wire()
    await finish(first)
    cache = json.loads(json.dumps(cache))
    await finish(reading_wire()[0])
    assert len(calls) == 1
    await finish(reading_wire('The report supplies a preliminary observation, not a regional estimate.')[0])
    assert len(calls) == 2
    with monkeypatch.context() as changed_projection:
        changed_projection.setattr(review, 'READING_CONTEXT_PROJECTION', 'source-reading-original-pointers/next')
        await finish(reading_wire()[0])
    assert len(calls) == 3
