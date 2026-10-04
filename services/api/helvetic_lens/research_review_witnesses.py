"""Shape and literal/evidence fences for a fallible final-answer reviewer."""
import re
from copy import deepcopy

WITNESS_POLICY = 'clause-bound-host-excerpts-and-scope/v6-explicit-enumerated-items'


def assertion_clauses(assertion):
    """Keep full sentences and require witnesses for their explicit list items."""
    # Keep the remaining tail intact after seven boundaries. The mandatory
    # overall judgment also checks relationships across these sentence spans.
    spans = re.split(r'(?<=[.!?])(?=\s+[A-Z])', assertion, maxsplit=7)
    result = {f'S{i}': span for i, span in enumerate(spans)}
    for i, span in enumerate(spans):
        available = 8 - len(result)
        if available < 2:
            break
        markers = list(re.finditer(r'\(([a-z]|[1-9][0-9]*)\)\s+', span))
        if len(markers) < 2 or not span[:markers[0].start()].rstrip().endswith(':'):
            continue
        labels = [item.group(1) for item in markers]
        ordered = (all(label.isdigit() for label in labels)
            and [int(label) for label in labels] == list(range(1, len(labels) + 1))) or (
                all(len(label) == 1 and label.isalpha() for label in labels)
                and [ord(label) for label in labels] == list(range(ord('a'), ord('a') + len(labels))))
        ends = [item.start() for item in markers[1:]] + [len(span)]
        if not ordered or any(not span[item.end():end].strip(' ,;:\n\t') for item, end in zip(markers, ends, strict=True)):
            continue
        # The original sentence remains mandatory, including its introduction,
        # modality, shared qualifiers and relationships. Added rows are exact
        # item spans to check within that parent, never inferred new claims.
        count = min(available, len(markers))
        for item in range(count):
            end = len(span) if item == count - 1 else markers[item + 1].start()
            result[f'S{i}.item{item + 1}'] = span[markers[item].start():end]
    return result


def witness_choices(references):
    """Short descriptive choices; the full unchanged original is host-owned."""
    return {f'{key}: {" ".join(ref["quote"].split())[:24]}': key
        for key, ref in references.items()}


def review_schema(assertion, references, concerns, *, point=True, delivered=()):
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
        props.update(reason={'type': 'string', 'maxLength': 600}, verdict={'type': 'string', 'enum': verdicts})
        return {'type': 'object', 'properties': props,
            'required': list(props), 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {
        'clauses': {'type': 'object', 'properties': {key: judgment(clause=True) for key in assertion_clauses(assertion)},
            'required': list(assertion_clauses(assertion)), 'additionalProperties': False}},
        'required': ['clauses'], 'additionalProperties': False}
    if not point:
        unresolved = {'type': 'string', 'enum': ['unresolved', 'answer_available', 'outside_request']}
        resolution = unresolved
        if delivered:
            resolution = {'anyOf': [
                {'type': 'array', 'minItems': 1, 'maxItems': len(delivered),
                    'items': {'type': 'string', 'enum': [item['point_id'] for item in delivered]}},
                unresolved]}
        schema['properties']['gap_resolution'] = resolution
        schema['required'].append('gap_resolution')
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
        relations = {}
        for witness in witnesses:
            key, relation = witness['key'], witness['scope_relation']
            if key in relations and relations[key] != relation:
                return 'duplicate_clause_witness'
            relations[key] = relation
    return None


def normalize_clause_witnesses(data, references):
    """Decode a shape-validated receipt; only originals supply literal text."""
    invalid = invalid_clause_witnesses(data, references)
    if invalid:
        raise ValueError(invalid)
    choices = witness_choices(references)
    result = deepcopy(data)
    if 'gap_resolution' in result:
        resolution = result.pop('gap_resolution')
        result['gap_status'] = 'answered' if isinstance(resolution, list) else resolution
        result['answer_point_ids'] = resolution if isinstance(resolution, list) else []
    for clause in result['clauses'].values():
        # The raw grammar permits repeated selections. Exact duplicates carry
        # no additional evidence; retain the first position without changing
        # the original receipt or resolving conflicting scope judgments.
        selections = dict.fromkeys((witness['key'], witness['scope_relation']) for witness in clause['witnesses'])
        clause['witnesses'] = [{'citation_ref': choices[key],
            'quote': references[choices[key]]['quote'],
            'scope_relation': relation} for key, relation in selections]
        clause['citation_refs'] = [witness['citation_ref'] for witness in clause['witnesses']]
    # Overall judges relationships across these same originals. It supplies its
    # own verdict, never a second citation selection or a host-inferred verdict.
    result['overall']['citation_refs'] = list(dict.fromkeys(ref
        for clause in result['clauses'].values() for ref in clause['citation_refs']))
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


def invalid_review(data, assertion, concerns, *, point, delivered=()):
    """Missing witnesses are a failed check, never a negative factual verdict."""
    if {c['id'] for c in data.get('concern_checks', [])} != set(concerns):
        return 'incomplete_concern_check'
    if set(data['clauses']) != set(assertion_clauses(assertion)):
        return 'incomplete_assertion_check'
    if not point:
        selected = data.get('answer_point_ids', [])
        available = {item['point_id'] for item in delivered}
        if (len(selected) != len(set(selected)) or any(key not in available for key in selected)
                or (data['gap_status'] == 'answered') != bool(selected)):
            return 'unbound_answered_gap'
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
