"""Owned source work, with literal requests separate from planner interpretations."""
import re
from copy import deepcopy

from .product_api import fail
from .product_operations import fingerprint

CONTRACT = 'requested-original-ownership/v1'
MATCH_CONTRACT = 'requested-original-match/v1'
FIELD = 'source_requirements'
TARGET_CONTRACT = 'source-target-ownership/v2'
TARGET_FIELD = 'source_targets'
TARGET_MATCH_CONTRACT = 'requested-original-match/v2'


def identifier(question, text):
    return fingerprint({'question': question, 'requested_source': text})


def target_identifier(question, text, origin):
    return fingerprint({'contract': TARGET_CONTRACT, 'question': question, 'source_target': text, 'origin': origin})


def validate_targets(values):
    """Validate interpreted names without claiming that they quote the user."""
    if not isinstance(values, list) or any(not isinstance(value, str)
            or not 3 <= len(value) <= 700 or len(value.strip()) < 3 for value in values):
        fail('Source targets must use bounded, nonblank source names.', 422, 'invalid_source_requirement')
    return list(dict.fromkeys(value.strip() for value in values))


def match_contract(requirement, question):
    return (MATCH_CONTRACT if requirement['id'] == identifier(question, requirement['requested_source'])
        else TARGET_MATCH_CONTRACT)


def validate_spans(question, values):
    """Only exact user text can become a planner's source acquisition task."""
    if not isinstance(values, list) or any(not isinstance(value, str)
            or not 3 <= len(value) <= 700 or value != value.strip() or value not in question
            for value in values):
        fail('Requested originals must use distinguishing exact text from the original question.',
            422, 'invalid_source_requirement')
    return list(dict.fromkeys(values))


def submitted_spans(question):
    """Keep literal user URLs only when the ordinary public path admitted them."""
    from .decision_search import public_url
    from .search_channels import explicit_sources

    admitted = {item['url'] for item in explicit_sources(question)}
    values = [raw.rstrip('.,;!?)') for raw in re.findall(r'https://[^\s<>"\']+', question)]
    return list(dict.fromkeys(value for value in values if public_url(value) in admitted))


def requirements(run, question_id=None):
    """Validate durable ownership against the current complete user question."""
    from .decision_search import public_url
    from .search_channels import explicit_sources

    question = run.question
    binding = fingerprint(question)
    admitted = {item['url'] for item in explicit_sources(question)}
    result, seen = [], set()
    for owner in run.research_state.get('questions', []):
        for field, contract in ((FIELD, CONTRACT), (TARGET_FIELD, TARGET_CONTRACT)):
            value = owner.get(field)
            if (not isinstance(value, dict) or value.get('contract') != contract
                    or value.get('question_fingerprint') != binding
                    or not isinstance(value.get('requirements'), list)):
                continue
            for item in value['requirements']:
                if not isinstance(item, dict):
                    continue
                text = item.get('requested_source')
                if not isinstance(text, str) or not 3 <= len(text) <= 700 or text != text.strip():
                    continue
                direct = public_url(text)
                if field == FIELD:
                    if text not in question or item.get('id') != identifier(question, text):
                        continue
                    origin = 'submitted_url' if direct and direct in admitted else 'literal_request'
                else:
                    origin = item.get('origin')
                    if (not isinstance(origin, str) or origin not in {'planner_interpretation', 'submitted_url'}
                            or item.get('id') != target_identifier(question, text, origin)
                            or origin == 'submitted_url' and text not in submitted_spans(question)):
                        continue
                if item['id'] in seen:
                    continue
                seen.add(item['id'])
                if question_id is not None and owner['id'] != question_id:
                    continue
                row = {'id': item['id'], 'requested_source': text, 'question_id': owner['id'], 'origin': origin}
                if origin == 'submitted_url' and direct and direct in admitted:
                    row['direct_url'] = direct
                result.append(row)
    return result


def attach(run, question_id, spans):
    """A repeated literal requirement retains its first admitted question owner."""
    spans = validate_spans(run.question, spans)
    if not spans:
        return
    data = deepcopy(run.research_state)
    owner = next((item for item in data.get('questions', []) if item['id'] == question_id), None)
    if owner is None:
        fail('A requested original needs an admitted research question.', 422, 'invalid_source_requirement')
    current = [item for item in requirements(run)
        if item['id'] == identifier(run.question, item['requested_source'])]
    owned = {item['id'] for item in current}
    values = [{key: item[key] for key in ('id', 'requested_source')}
        for item in current if item['question_id'] == question_id]
    values.extend({'id': identifier(run.question, text), 'requested_source': text}
        for text in spans if identifier(run.question, text) not in owned)
    if values:
        owner[FIELD] = {'contract': CONTRACT, 'question_fingerprint': fingerprint(run.question),
            'requirements': values}
        run.research_state = data


def attach_targets(run, question_id, names, *, origin='planner_interpretation'):
    """Only planning admits interpreted targets; submitted URLs are host-owned."""
    names = validate_targets(names)
    if not isinstance(origin, str) or origin not in {'planner_interpretation', 'submitted_url'} or (
            origin == 'submitted_url' and any(name not in submitted_spans(run.question) for name in names)):
        fail('Submitted source authority requires an admitted literal user URL.', 422, 'invalid_source_requirement')
    if not names:
        return
    data = deepcopy(run.research_state)
    owner = next((item for item in data.get('questions', []) if item['id'] == question_id), None)
    if owner is None:
        fail('A source target needs an admitted research question.', 422, 'invalid_source_requirement')
    current = [item for item in requirements(run)
        if item['id'] != identifier(run.question, item['requested_source'])]
    owned = {item['id'] for item in current}
    values = [{key: item[key] for key in ('id', 'requested_source', 'origin')}
        for item in current if item['question_id'] == question_id]
    values.extend({'id': target_identifier(run.question, name, origin), 'requested_source': name, 'origin': origin}
        for name in names if target_identifier(run.question, name, origin) not in owned)
    if values:
        owner[TARGET_FIELD] = {'contract': TARGET_CONTRACT, 'question_fingerprint': fingerprint(run.question),
            'requirements': values}
        run.research_state = data


def retain_matches(run, source, matches):
    """Keep independently valid cited identity notes, never reading completion."""
    from .config import DomainError
    from .product_investigations import citation
    from .product_requested_originals import valid_match

    wanted = {item['id']: item for item in requirements(run)}
    if not wanted:
        return
    binding = fingerprint(run.question)
    def current(value):
        if not isinstance(value, dict) or not isinstance(value.get('requirement_id'), str):
            return False
        requirement = wanted.get(value.get('requirement_id'))
        return requirement is not None and valid_match(value, source, requirement, run.question)

    previous = source.snapshot.get('requested_source_matches', [])
    retained = {value['requirement_id']: deepcopy(value)
        for value in (previous if isinstance(previous, list) else []) if current(value)}
    for proposed in matches:
        requirement = wanted.get(proposed.requirement_id)
        if requirement is None or proposed.source_id != source.id:
            continue
        try:
            pin = citation(source, proposed)
        except DomainError:
            continue  # Optional identification cannot discard completed document reading.
        contract = match_contract(requirement, run.question)
        value = {'contract': contract, 'question_fingerprint': binding,
            'requirement_id': requirement['id'], 'requested_source': requirement['requested_source'],
            'identity': {key: pin[key] for key in ('source_id', 'sha256', 'locator', 'quote')}}
        if contract == TARGET_MATCH_CONTRACT:
            value['origin'] = requirement['origin']
        if current(value):
            retained[requirement['id']] = value
    if retained or 'requested_source_matches' in source.snapshot:
        source.snapshot = {**source.snapshot, 'requested_source_matches': list(retained.values())}
