"""Answer transport preserves complete prose; scripted output is not semantic proof."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import product_exploration as exploration
from helvetic_lens.config import DomainError
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request
from helvetic_lens.research_model_transport import EvidenceWire

SHORT = 'The fictional archive permits supervised access.'
LONG = (
    'The fictional archive permits supervised access to the deposited material when the '
    'owner has supplied written permission, the visitor uses the designated reading room, '
    'and the archivist can provide the requested material without exposing another owner’s '
    'restricted records. This permission concerns consultation of the deposited originals; '
    'it does not itself authorize publication, copying for distribution, or removal of material '
    'from the archive. Where the owner has expressly permitted reproduction, a visitor must '
    'retain the supplied attribution and any restriction that applies to the particular item. '
    'A permission for one deposit does not automatically extend to other deposits by the same '
    'owner. The archive can provide an alternative appointment if supervision is unavailable, '
    'but that administrative arrangement neither expands the owner’s permission nor establishes '
    'that access to other collections is unrestricted. These conditions apply to the fictional '
    'archive described in the cited record.'
)


def fixture():
    source = {'id': 'archive', 'kind': 'public_source', 'sha256': 'a' * 64,
        'title': 'Fictional archive conditions', 'excerpts': [
            {'passage': 'p1', 'text': 'The archive permits supervised consultation with written owner permission. '
                'Publication, distributed copies and removal require separate authorization. '
                'Permitted reproductions retain attribution and item restrictions.'},
            {'passage': 'p2', 'text': 'Permission is specific to each deposit. An alternative supervised appointment '
                'does not expand permission or establish unrestricted access to other collections.'}]}
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'What access does this archive permit and on what conditions?',
        'research_mission': {}, 'sources': [source]}}
    schema = mission_schema(exploration.Briefing)
    return EvidenceWire(work, schema, ''), schema, source


@pytest.mark.parametrize('statement,refs', [(SHORT, [1]), (LONG, [1]), (LONG, [1, 2])])
def test_complete_answer_survives_wire_typed_storage_and_exact_citation_validation(monkeypatch, statement, refs):
    wire, schema, source = fixture()
    raw = {'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
        {'statement': statement, 'evidence': [{'citation_ref': ref, 'role': 'support'} for ref in refs]}]},
        'next_action': 'finish'}
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    restored = schema.model_validate_json(parsed.model_dump_json())
    point = restored.mission_checkpoint.answer.points[0]
    assert point.statement == statement
    assert [ref.model_dump() for ref in point.evidence] == [
        {**wire.references[ref], 'role': 'support'} for ref in refs]
    # The legacy card cannot impose its narrower prose contract on the answer.
    assert [finding.statement for finding in restored.findings] == ([SHORT] if statement == SHORT else [])
    current = SimpleNamespace(id=source['id'], sha256=source['sha256'], snapshot=deepcopy(source))
    monkeypatch.setattr(exploration, 'sources', lambda session, run: {current.id: current})
    saved = exploration.validated_question_points(None, None, wire.input, restored.mission_checkpoint.answer)
    serialized = json.loads(json.dumps(saved))
    assert serialized['points'][0]['statement'] == statement
    assert all(ref['sha256'] == source['sha256'] and ref['independently_verified'] is False
        for ref in serialized['points'][0]['evidence'])
    current.snapshot['excerpts'] = [{'passage': 'p1', 'text': 'The original has changed.'}]
    with pytest.raises(DomainError) as caught:
        exploration.validated_question_points(None, None, wire.input, restored.mission_checkpoint.answer)
    assert caught.value.code == 'invalid_evidence'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['factual', 'citations', 'forged_citation'])
async def test_complete_correction_and_resumed_proposal_preserve_text_and_evidence(mode):
    wire, _, _ = fixture()
    checkpoints, calls = {}, []
    correction = {'previous_statement': LONG if mode == 'citations' else SHORT, 'validation_errors': []}
    if mode == 'citations':
        correction['edit_scope'] = 'citations'

    class Model:
        async def complete(self, system, text, **options):
            calls.append(json.loads(text))
            item = {'evidence': [{'citation_ref': 999 if mode == 'forged_citation' else 1, 'role': 'support'},
                {'citation_ref': 2, 'role': 'context'}]}
            if mode != 'citations':
                item['statement'] = LONG
            return json.dumps({'points': [item]})

    service = SimpleNamespace(model_client=Model())
    points, gap, receipt = await answer_request(service, wire, wire.input['original_question'], 60,
        correction=correction, preselected_references=wire.references, checkpoints=checkpoints)
    assert gap == '' and len(calls) == 1
    if mode == 'forged_citation':
        assert not points and receipt['status'] == 'invalid_answer'
        return
    assert receipt['status'] == 'proposed'
    assert len(LONG) > 700 and points[0].statement == LONG
    assert [ref.model_dump() for ref in points[0].evidence] == [
        {**wire.references[1], 'role': 'support'}, {**wire.references[2], 'role': 'context'}]
    resumed, resumed_gap, resumed_receipt = await answer_request(service, wire, wire.input['original_question'], 0,
        correction=correction, preselected_references=wire.references,
        checkpoints=json.loads(json.dumps(checkpoints)))
    assert resumed == points and resumed_gap == '' and resumed_receipt['status'] == 'proposed'
    assert len(calls) == 1
