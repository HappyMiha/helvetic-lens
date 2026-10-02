"""Shape and literal/evidence fences for a fallible final-answer reviewer."""
import re


def assertion_clauses(assertion):
    """Exact sentence spans; shared verbs and qualifications stay together."""
    # Keep the remaining tail intact after seven boundaries. The mandatory
    # overall judgment also checks relationships across these sentence spans.
    spans = re.split(r'(?<=[.!?])(?=\s+[A-Z])', assertion, maxsplit=7)
    return {f'S{i}': span for i, span in enumerate(spans)}


def review_schema(assertion, references, concerns, *, point=True):
    refs = {'type': 'array', 'items': {'type': 'integer', **({'enum': list(references)} if references else {})},
        'maxItems': min(8, len(references))}
    def judgment():
        # Conditional witnesses are enforced by invalid_review before any
        # judgment is accepted or cached. Repeating this entire object for
        # each verdict wastes the request allowance needed by the originals.
        verdicts = [verdict for verdict in ('supported', 'contradicted', 'not_established')
            if references or not (verdict == 'contradicted' or point and verdict == 'supported')]
        props = {'verdict': {'type': 'string', 'enum': verdicts},
            'reason': {'type': 'string', 'maxLength': 200},
            'citation_refs': {**refs, 'minItems': 0}}
        return {'type': 'object', 'properties': props,
            'required': list(props), 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {'overall': judgment(),
        'clauses': {'type': 'object', 'properties': {key: judgment() for key in assertion_clauses(assertion)},
            'required': list(assertion_clauses(assertion)), 'additionalProperties': False}},
        'required': ['overall', 'clauses'], 'additionalProperties': False}
    if not point:
        schema['properties']['gap_status'] = {'type': 'string', 'enum': ['unresolved', 'answered', 'answer_available', 'outside_request']}
        schema['required'].append('gap_status')
    if concerns:
        props = {'id': {'type': 'string', 'enum': list(concerns)},
            'outcome': {'type': 'string', 'enum': ['resolved', 'remains', 'cannot_assess'] if references else ['cannot_assess']},
            'reason': {'type': 'string', 'maxLength': 200},
            'citation_refs': {**refs, 'minItems': 0}}
        schema['properties']['concern_checks'] = {'type': 'array', 'minItems': len(concerns), 'maxItems': len(concerns),
            'items': {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}}
        schema['required'].append('concern_checks')
    return schema


def invalid_review(data, assertion, concerns, *, point):
    """Missing witnesses are a failed check, never a negative factual verdict."""
    if {c['id'] for c in data.get('concern_checks', [])} != set(concerns):
        return 'incomplete_concern_check'
    if set(data['clauses']) != set(assertion_clauses(assertion)):
        return 'incomplete_assertion_check'
    # The serving JSON grammar does not implement uniqueItems.
    if any(len(c['citation_refs']) != len(set(c['citation_refs']))
            for c in [data['overall'], *data['clauses'].values(), *data.get('concern_checks', [])]):
        return 'duplicate_original_witness'
    for clause in [data['overall'], *data['clauses'].values()]:
        if (clause['verdict'] == 'contradicted' or point and clause['verdict'] == 'supported') and not clause['citation_refs']:
            return 'missing_original_witness'
    if any(c['outcome'] in {'resolved', 'remains'} and not c['citation_refs'] for c in data.get('concern_checks', [])):
        return 'missing_concern_witness'
    return None
