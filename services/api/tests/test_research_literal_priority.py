"""Requested answers must not lose their capacity to generated background gaps."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_final_review import finalize
from helvetic_lens.research_model_transport import EvidenceWire

BASE = [
    'North Reach operates the registry.',
    'The registry keeps the current permit records.',
    'Applicants can inspect the public register.',
    'A permit requires a signature and remains limited to its named site.',
    'The registry records the authority that signs each permit.',
    'The register distinguishes current permits from withdrawn permits.',
    'The registry retains the published permit notices.',
    'Applicants can request a copy of their permit.',
]
REQUESTS = ['What makes the permit effective?', 'What happens when it is withdrawn?']
ANSWERS = ['A signature makes the permit effective; it remains limited to its named site.',
    'Withdrawal ends the permit validity and the registry marks it withdrawn.']
OPTIONAL = ['An exact long-term average processing time is not supplied.',
    'A complete ranking of all registry offices is not supplied.']
UNCERTAINTY = 'The record does not establish whether an unsigned permit was ever used.'


def fixture(count, *, missing=REQUESTS, limitations=(), legacy=False):
    question = 'Who operates the registry? ' + ' '.join(missing)
    texts = [*BASE, *ANSWERS, UNCERTAINTY]
    work = {'phase': 'brief', 'input': {'original_question': question, 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'title': 'Registry rules',
            'url': 'https://example.org/registry',
            'excerpts': [{'passage': f'paragraph-{index}', 'text': text} for index, text in enumerate(texts)]}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    refs = {ref['quote']: ref for ref in wire.references.values()}
    answer = AssessmentOutcome(status='partial', points=[{'statement': text,
        'evidence': [{**refs[text], 'role': 'support'}]} for text in BASE[:count]], limitations=list(limitations))
    if legacy:
        wire.request_keys = {'r1': missing[0]}
        wire.point_requests = ['r1'] * count
        wire.response_slots = {'r1': {'disposition': 'unresolved', 'remaining_gap': limitations[0]}}
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    return work, wire, parsed


def use_coverage(monkeypatch, expected):
    async def advisory(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'points_checked': len(args[3].points)}

    async def coverage(settings, work, wire, answer, seconds, **kwargs):
        statements = {point.statement for point in answer.points}
        missing = [request for request, statement in expected.items() if statement not in statements]
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered',
            'decisions': [], 'hints': [{'path': ['answer'], 'review_signal': 'requested_part_missing',
                'user_request': request, 'instruction': 'Answer this literal request from its originals.'} for request in missing]}

    monkeypatch.setattr(review, 'audit_points', advisory)
    monkeypatch.setattr(review, 'audit', coverage)


class Model:
    def __init__(self, answers, *, full=False, empty=False, rejected=False, unassessed=False):
        self.answers, self.full, self.empty, self.rejected = answers, full, empty, rejected
        self.unassessed = unassessed
        self.writers, self.checked = [], []

    async def complete(self, system, text, **options):
        value = json.loads(text)
        if 'final_claims_and_gaps' in value:
            item = next(iter(value['final_claims_and_gaps'].values()))
            claim = item.get('statement', item.get('gap'))
            self.checked.append(claim)
            selected = value.get('selected_citation_refs', [])
            verdict = 'not_established' if claim in OPTIONAL or (self.rejected and claim == ANSWERS[0]) else 'supported'
            judgment = {'verdict': verdict, 'reason': 'The exact supplied original establishes the scope.' if verdict == 'supported' else 'The originals do not establish this absence claim.',
                'citation_refs': selected if verdict == 'supported' else []}
            response = {'overall': judgment, 'clauses': {key: judgment for key in value['assertion_clauses']}}
            if 'gap' in item:
                response['gap_status'] = 'unresolved'
            if value.get('prior_review_concerns'):
                # A replacement must retain both its original qualification and
                # the newly selected evidence through the actual review pack.
                assert self.full and claim == ANSWERS[0]
                assert BASE[3] in text and ANSWERS[0] in text
                response['concern_checks'] = [{'id': key, 'outcome': 'cannot_assess' if self.unassessed else 'remains' if self.rejected else 'resolved',
                    'reason': 'The cited originals retain the site qualification and establish the signature effect.',
                    'citation_refs': [] if self.unassessed else selected} for key in value['prior_review_concerns']['concerns']]
            return json.dumps(response)
        schema = options['response_schema']
        if 'citation_refs' in schema['properties']:
            return json.dumps({'citation_refs': {key: node['items']['enum']
                for key, node in schema['properties']['citation_refs']['properties'].items()}})
        assert value['requested_part'] in self.answers, 'A generated optional gap must not become a new writing task'
        choices = schema['properties']['replace_point']['enum']
        assert ('new' in choices) != self.full
        self.writers.append(value['requested_part'])
        answer = self.answers[value['requested_part']]
        ref = next(passage['citation_ref'] for source in value['sources'] for passage in source['passages']
            if passage['text'] == answer)
        return json.dumps({'points': [] if self.empty else [{'statement': answer,
            'evidence': [{'citation_ref': ref, 'role': 'support'}]}],
            'remaining_gap': 'The requested effect remains unresolved.' if self.empty else '',
            'replace_point': 'P3' if self.full else 'new'})


@pytest.mark.asyncio
async def test_literal_requests_use_capacity_before_optional_generated_gaps(monkeypatch):
    expected = dict(zip(REQUESTS, ANSWERS))
    work, wire, parsed = fixture(5, limitations=[*OPTIONAL, UNCERTAINTY])
    original = deepcopy(parsed.mission_checkpoint.answer.points)
    use_coverage(monkeypatch, expected)
    model = Model(expected)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=model)
    # An older completed gap-first plan must not suppress current literal repair.
    cache = {'final_correction_round': {'tasks': [], 'observations': [], 'completed': 0, 'receipts': []}}
    result = await finalize(service, work, wire, parsed, 90, checkpoints=cache)
    answer = parsed.mission_checkpoint.answer
    assert model.writers == REQUESTS
    assert answer.points[:5] == original and [point.statement for point in answer.points[5:]] == ANSWERS
    assert len(answer.points) == 7 and result['question_coverage'] == 'covered'
    assert UNCERTAINTY in answer.limitations and not set(OPTIONAL) & set(answer.limitations)
    assert cache['final_correction_round']['contract'] == 'literal-request-repair/v1'
    assert all(task['focus'] in REQUESTS for task in cache['final_correction_round']['tasks'])
    assert all(receipt['status'] == 'proposed' for receipt in cache['final_correction_round']['receipts'])
    assert all(model.checked.count(point.statement) == 1 for point in original)


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['amend', 'empty', 'rejected', 'unassessed'])
async def test_full_answer_amends_or_keeps_request_missing_without_discarding_new_work(monkeypatch, outcome):
    empty = outcome == 'empty'
    expected = {REQUESTS[0]: ANSWERS[0]}
    work, wire, parsed = fixture(8, missing=[REQUESTS[0]])
    original = deepcopy(parsed.mission_checkpoint.answer.points)
    use_coverage(monkeypatch, expected)
    model = Model(expected, full=True, empty=empty, rejected=outcome == 'rejected', unassessed=outcome == 'unassessed')
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=model)
    cache = {}
    result = await finalize(service, work, wire, parsed, 90, checkpoints=cache)
    answer = parsed.mission_checkpoint.answer
    assert model.writers == [REQUESTS[0]] and len(answer.points) == 8
    assert answer.points[:3] == original[:3] and answer.points[4:] == original[4:]
    receipt = cache['final_correction_round']['receipts'][0]
    assert receipt['status'] != 'unrepresented'
    if outcome != 'amend':
        assert answer.points == original and result['question_coverage'] == 'missing'
        assert [hint['user_request'] for hint in result['hints']] == [REQUESTS[0]]
    else:
        assert answer.points[3].statement == ANSWERS[0]
        assert answer.points[3].evidence[0].quote == ANSWERS[0]
        assert result['question_coverage'] == 'covered' and receipt['replace_point'] == 'P3'
        assert model.checked.count(ANSWERS[0]) == 1
    assert all(model.checked.count(point.statement) == 1 for point in original)


@pytest.mark.asyncio
async def test_owned_gap_and_missing_request_share_one_literal_repair(monkeypatch):
    expected = {REQUESTS[0]: ANSWERS[0]}
    work, wire, parsed = fixture(5, missing=[REQUESTS[0]], limitations=[OPTIONAL[0]], legacy=True)
    use_coverage(monkeypatch, expected)
    model = Model(expected)
    cache = {}
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=model),
        work, wire, parsed, 90, checkpoints=cache)
    assert model.writers == [REQUESTS[0]] and len(cache['final_correction_round']['tasks']) == 1
    assert cache['final_correction_round']['tasks'][0]['gaps'] == [OPTIONAL[0]]
    assert wire.response_slots['r1'] == {'disposition': 'answered', 'remaining_gap': ''}
    assert result['question_coverage'] == 'covered' and not parsed.mission_checkpoint.answer.limitations
