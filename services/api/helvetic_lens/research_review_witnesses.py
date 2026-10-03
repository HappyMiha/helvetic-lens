"""Shape and literal/evidence fences for a fallible final-answer reviewer."""
import re
from copy import deepcopy

WITNESS_POLICY = 'clause-bound-host-excerpts-and-scope/v3'


def assertion_clauses(assertion):
    """Exact sentence spans; shared verbs and qualifications stay together."""
    # Keep the remaining tail intact after seven boundaries. The mandatory
    # overall judgment also checks relationships across these sentence spans.
    spans = re.split(r'(?<=[.!?])(?=\s+[A-Z])', assertion, maxsplit=7)
    return {f'S{i}': span for i, span in enumerate(spans)}


def witness_choices(references):
    """Short descriptive choices; the full unchanged original is host-owned."""
    return {f'{key}: {" ".join(ref["quote"].split())[:24]}': key
        for key, ref in references.items()}


def review_schema(assertion, references, concerns, *, point=True):
    refs = {'type': 'array', 'items': {'type': 'integer', **({'enum': list(references)} if references else {})},
        'maxItems': min(8, len(references))}
    def judgment(*, clause=False):
        # Conditional witnesses are enforced by invalid_review before any
        # judgment is accepted or cached. Repeating this entire object for
        # each verdict wastes the request allowance needed by the originals.
        verdicts = [verdict for verdict in ('supported', 'contradicted', 'not_established')
            if references or not (verdict == 'contradicted' or point and verdict == 'supported')]
        props = {}
        if clause:
            witness = {'key': {'type': 'string', **({'enum': list(witness_choices(references))} if references else {})},
                'scope_relation': {'type': 'string', 'enum': ['compatible', 'different', 'not_established']}}
            props['witnesses'] = {'type': 'array', 'maxItems': min(8, len(references)),
                'items': {'type': 'object', 'properties': witness,
                    'required': list(witness), 'additionalProperties': False}}
        else:
            props['citation_refs'] = {**refs, 'minItems': 0}
        props.update(reason={'type': 'string', 'maxLength': 600}, verdict={'type': 'string', 'enum': verdicts})
        return {'type': 'object', 'properties': props,
            'required': list(props), 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {
        'clauses': {'type': 'object', 'properties': {key: judgment(clause=True) for key in assertion_clauses(assertion)},
            'required': list(assertion_clauses(assertion)), 'additionalProperties': False}},
        'required': ['clauses'], 'additionalProperties': False}
    if not point:
        schema['properties']['gap_status'] = {'type': 'string', 'enum': ['unresolved', 'answered', 'answer_available', 'outside_request']}
        schema['required'].append('gap_status')
    if concerns:
        def concern(outcomes, minimum):
            props = {'id': {'type': 'string', 'enum': list(concerns)},
                'outcome': {'type': 'string', 'enum': outcomes},
                'reason': {'type': 'string', 'maxLength': 600},
                'citation_refs': {**refs, 'minItems': minimum}}
            return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}
        # Match the existing host conditional witness rule in the serving
        # grammar. Only concern judgments need these two compact alternatives;
        # uncertainty can still be returned honestly without inventing evidence.
        unavailable = concern(['cannot_assess'], 0)
        item = {'anyOf': [concern(['resolved', 'remains'], 1), unavailable]} if references else unavailable
        schema['properties']['concern_checks'] = {'type': 'array', 'minItems': len(concerns), 'maxItems': len(concerns),
            'items': item}
        schema['required'].append('concern_checks')
    schema['properties']['overall'] = judgment()
    schema['required'].append('overall')
    return schema


def invalid_clause_witnesses(data, references):
    """Only supplied choices can name evidence; failure is unavailable review."""
    choices = witness_choices(references)
    for clause in data['clauses'].values():
        witnesses = clause['witnesses']
        keys = [witness['key'] for witness in witnesses]
        if any(key not in choices for key in keys):
            return 'unbound_clause_witness'
        if len(keys) != len(set(keys)):
            return 'duplicate_clause_witness'
    return None


def normalize_clause_witnesses(data, references):
    """Derive citations and literal text; model prose never becomes a quote."""
    invalid = invalid_clause_witnesses(data, references)
    if invalid:
        raise ValueError(invalid)
    choices = witness_choices(references)
    result = deepcopy(data)
    for clause in result['clauses'].values():
        clause['witnesses'] = [{'citation_ref': choices[witness['key']],
            'quote': references[choices[witness['key']]]['quote'],
            'scope_relation': witness['scope_relation']} for witness in clause['witnesses']]
        clause['citation_refs'] = [witness['citation_ref'] for witness in clause['witnesses']]
    return result


def enforce_clause_scope(data):
    """An explicit scope mismatch cannot be overruled by a positive verdict."""
    for clause in data['clauses'].values():
        mismatches = [witness for witness in clause['witnesses'] if witness['scope_relation'] != 'compatible']
        if mismatches and clause['verdict'] in {'supported', 'contradicted'}:
            clause['verdict'] = 'not_established'
            comparison = ', '.join(f"{witness['citation_ref']}: {witness['scope_relation']}" for witness in mismatches)
            clause['reason'] = (f'The quoted originals do not establish the assertion\'s scope ({comparison}). ' + clause['reason'])[:600]
        if mismatches and data.get('gap_status') in {'answered', 'answer_available'}:
            data['gap_status'] = 'unresolved'
    return data


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
