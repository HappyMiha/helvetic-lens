"""A whole-question amendment preserves independent findings and exact targets."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model

from helvetic_lens import research_answer_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import AGGREGATE_POLICY, answer_request
from helvetic_lens.research_final_review import finalize
from helvetic_lens.research_model_transport import EvidenceWire

ORIGINAL = ['North Reach operates the registry.', 'Permits require a signature.',
    'The register retains withdrawal notices.']
IMPROVED = ['Permits require a signature and apply only to the named site.',
    'The register retains withdrawal notices and records when validity ends.',
    'Applicants can inspect the public register.']
GAP = 'The retained record does not establish whether any unsigned permit was used.'


def fixture():
    question = ('Who operates the registry? What makes a permit effective and where does it apply? '
        'What withdrawal information is kept? Can applicants inspect the register? Was any unsigned permit used?')
    work = {'phase': 'brief', 'input': {'original_question': question, 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'title': 'Registry record',
            'url': 'https://example.org/registry', 'excerpts': [
                {'passage': f'paragraph-{i}', 'text': text} for i, text in enumerate([*ORIGINAL, *IMPROVED, GAP])]}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    refs = {ref['quote']: ref for ref in wire.references.values()}
    answer = AssessmentOutcome(status='partial', points=[{'statement': text,
        'evidence': [{**refs[text], 'role': 'support'}]} for text in ORIGINAL], limitations=[GAP])
    return work, wire, SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))


class Model:
    def __init__(self, *, reject=False, interrupt=False, invalid=None, interrupt_writer=False, full=False):
        self.reject, self.interrupt, self.invalid = reject, interrupt, invalid
        self.interrupt_writer, self.full = interrupt_writer, full
        self.writers, self.checked, self.outputs = [], [], []

    @atomic_pack_model
    async def complete(self, system, text, **options):
        value = json.loads(text)
        schema = options['response_schema']
        if 'final_claims_and_gaps' in value:
            item = next(iter(value['final_claims_and_gaps'].values()))
            statement = item.get('statement', item.get('gap'))
            self.checked.append(statement)
            if self.interrupt and statement == IMPROVED[0]:
                self.interrupt = False
                raise DomainError('Synthetic interruption', 503, 'model_upstream_timeout')
            passages = [p for s in value.get('source_context', value.get('sources', [])) for p in s['passages']]
            refs = value.get('selected_citation_refs') or [p['citation_ref'] for p in passages if p['text'] == statement]
            rejected = self.reject and statement == IMPROVED[1]
            judgment = {'verdict': 'not_established' if rejected else 'supported',
                'reason': 'Synthetic unvalidated replacement.' if rejected else '',
                'citation_refs': [] if rejected else refs}
            result = {'overall': judgment, 'clauses': {key: judgment for key in value['assertion_clauses']}}
            if 'gap' in item:
                result['gap_status'] = 'unresolved'
            if value.get('prior_review_concerns'):
                # Each replacement must carry only its own original obligation.
                expected = ORIGINAL[1] if statement == IMPROVED[0] else ORIGINAL[2]
                concerns = value['prior_review_concerns']
                assert concerns['previous_statements'] == [expected]
                result['concern_checks'] = [{'id': key, 'outcome': 'remains' if rejected else 'resolved',
                    'reason': 'Synthetic outcome for this exact target.', 'citation_refs': refs}
                    for key in concerns['concerns']]
            return json.dumps(result)
        if 'citation_refs' in schema['properties']:
            return json.dumps({'citation_refs': {key: item['items']['enum']
                for key, item in schema['properties']['citation_refs']['properties'].items()}})
        self.writers.append(value)
        self.outputs.append(options['max_output_tokens'])
        assert 'replace_point' not in schema['properties']
        props = schema['properties']['points']['items']['properties']
        assert props['replace_point']['enum'] == [*(['new'] if value['new_point_capacity'] else []), *value['retained_answer']]
        assert value['retained_gaps'] == [GAP]
        assert 'retained_gaps' not in value.get('review_feedback', {})
        if self.interrupt_writer:
            self.interrupt_writer = False
            raise DomainError('Synthetic writer interruption', 503, 'model_upstream_timeout')
        refs = {p['text']: p['citation_ref'] for s in value['sources'] for p in s['passages']}
        points = [{'statement': statement, 'replace_point': target,
            'evidence': [{'citation_ref': refs[statement], 'role': 'support'}]}
            for statement, target in zip(IMPROVED, ['P1', 'P2', 'new'], strict=True)]
        if self.full:
            assert value['new_point_capacity'] == 0
            points.pop()
        if self.invalid == 'duplicate_target':
            points[1]['replace_point'] = 'P1'
        elif self.invalid == 'unknown_target':
            points[1]['replace_point'] = 'P99'
        elif self.invalid == 'excess_additions':
            for point in points:
                point['replace_point'] = 'new'
        elif self.invalid == 'duplicate_sibling':
            points[0].update(statement=ORIGINAL[0], evidence=[{'citation_ref': refs[ORIGINAL[0]], 'role': 'support'}])
        return json.dumps({'points': points, 'remaining_gap': GAP})


def coverage(monkeypatch, question):
    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def assess(settings, work, wire, answer, seconds, **kwargs):
        complete = set(IMPROVED) <= {point.statement for point in answer.points}
        return {'status': 'checked', 'question_coverage': 'covered' if complete else 'missing', 'decisions': [],
            'hints': [] if complete else [{'path': ['answer'], 'review_signal': 'requested_part_missing',
                'user_request': question, 'instruction': 'Complete the original question from retained originals.'}]}

    monkeypatch.setattr(review, 'audit_points', fast)
    monkeypatch.setattr(review, 'audit', assess)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['complete', 'interrupted', 'writer_interrupted', 'rejected_replacement'])
async def test_whole_question_amendment_retains_siblings_and_per_target_resume(monkeypatch, mode):
    work, wire, parsed = fixture()
    original = deepcopy(parsed.mission_checkpoint.answer.points)
    coverage(monkeypatch, work['input']['original_question'])
    model = Model(interrupt=mode == 'interrupted', interrupt_writer=mode == 'writer_interrupted',
        reject=mode == 'rejected_replacement')
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=model)
    saved = {}
    if mode in {'interrupted', 'writer_interrupted'}:
        with pytest.raises(DomainError):
            await finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert saved['final_correction_round']['completed'] == (0 if mode == 'writer_interrupted' else 1)
        if mode == 'writer_interrupted':
            assert parsed.mission_checkpoint.answer.points == original
        saved = json.loads(json.dumps(saved))
    result = await finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    answer = parsed.mission_checkpoint.answer
    attempts = 2 if mode == 'writer_interrupted' else 1
    assert len(model.writers) == attempts and model.outputs == [8192] * attempts
    assert answer.points[0] == original[0] and len(answer.points) == 4
    assert answer.points[1].statement == IMPROVED[0]
    assert answer.points[2] == original[2] if mode == 'rejected_replacement' else answer.points[2].statement == IMPROVED[1]
    assert answer.points[3].statement == IMPROVED[2] and GAP in answer.limitations
    assert all(model.checked.count(point.statement) == 1 for point in original)
    assert result['question_coverage'] == ('missing' if mode == 'rejected_replacement' else 'covered')
    receipt = saved['final_correction_round']['receipts'][0]
    assert receipt['replacement_targets'] == ['P1', 'P2', 'new']
    assert receipt['amendment_contract'] == AGGREGATE_POLICY
    assert len(saved['amendment_fallbacks']) == 2


@pytest.mark.asyncio
async def test_full_aggregate_answer_can_replace_two_targets_without_appending(monkeypatch):
    work, _, parsed = fixture()
    extras = ['The registry preserves signed forms.', 'The registry records the named site.',
        'The register lists current permits.', 'The register distinguishes withdrawn permits.',
        'The registry retains its published notices.']
    work['input']['sources'][0]['excerpts'].extend({'passage': f'appendix-{i}', 'text': text}
        for i, text in enumerate(extras))
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    originals = {ref['quote']: ref for ref in wire.references.values()}
    parsed.mission_checkpoint.answer.points.extend(type(parsed.mission_checkpoint.answer.points[0])(
        statement=text, evidence=[{**originals[text], 'role': 'support'}]) for text in extras)
    before = deepcopy(parsed.mission_checkpoint.answer.points)
    coverage(monkeypatch, work['input']['original_question'])
    model, saved = Model(full=True), {}
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=model),
        work, wire, parsed, 90, checkpoints=saved)
    points = parsed.mission_checkpoint.answer.points
    assert len(points) == 8 and points[0] == before[0] and points[3:] == before[3:]
    assert [point.statement for point in points[1:3]] == IMPROVED[:2]
    assert saved['final_correction_round']['receipts'][0]['replacement_targets'] == ['P1', 'P2']
    assert result['question_coverage'] == 'missing', 'Unanswered inspection request must not be inferred from replacements'
    assert all(model.checked.count(point.statement) == 1 for point in before)


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['duplicate_target', 'unknown_target', 'excess_additions', 'duplicate_sibling'])
async def test_invalid_aggregate_targets_cannot_mutate_or_hide_retained_points(invalid):
    work, wire, parsed = fixture()
    amendments = {f'P{i}': point.model_dump() for i, point in enumerate(parsed.mission_checkpoint.answer.points)}
    before = deepcopy(amendments)
    model = Model(invalid=invalid)
    points, gap, receipt = await answer_request(SimpleNamespace(model_client=model), wire,
        work['input']['original_question'], 60, amendments=amendments, append_capacity=1, max_points=4,
        feedback={'retained_gaps': [GAP]})
    assert not points and receipt['status'] == 'invalid_answer'
    assert amendments == before and parsed.mission_checkpoint.answer.points[0].statement == ORIGINAL[0]


@pytest.mark.asyncio
async def test_aggregate_cache_binds_capacity_targets_sources_and_validates_raw_choices():
    work, wire, parsed = fixture()
    amendments = {f'P{i}': point.model_dump() for i, point in enumerate(parsed.mission_checkpoint.answer.points)}
    model, saved = Model(), {}
    service = SimpleNamespace(model_client=model)
    options = {'amendments': amendments, 'append_capacity': 2, 'max_points': 5, 'feedback': {'retained_gaps': [GAP]}}
    points, gap, receipt = await answer_request(service, wire, work['input']['original_question'], 60,
        checkpoints=saved, **options)
    assert len(points) == 3 and gap == GAP and model.outputs == [5800]
    again, _, repeated = await answer_request(service, wire, work['input']['original_question'], 0,
        checkpoints=json.loads(json.dumps(saved)), **options)
    assert again == points and repeated['replacement_targets'] == ['P1', 'P2', 'new'] and len(model.writers) == 1
    damaged = deepcopy(saved)
    damaged[receipt['input_fingerprint']]['draft']['points'][1]['replace_point'] = 'P99'
    rejected, _, invalid = await answer_request(service, wire, work['input']['original_question'], 0,
        checkpoints=damaged, **options)
    assert rejected == [] and invalid['status'] == 'invalid_answer' and len(model.writers) == 1
    for change in ('capacity', 'target', 'source'):
        changed = deepcopy(options)
        if change == 'capacity':
            changed['append_capacity'] = 1
        elif change == 'target':
            changed['amendments']['P1']['statement'] += ' Its qualification changed.'
        else:
            wire.references[1]['quote'] += ' The record was revised.'
        _, _, fresh = await answer_request(service, wire, work['input']['original_question'], 0,
            checkpoints=saved, **changed)
        assert fresh['input_fingerprint'] != receipt['input_fingerprint'] and fresh['status'] == 'unavailable'
    assert len(model.writers) == 1
