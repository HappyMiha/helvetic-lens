"""Shape and literal/evidence fences for a fallible final-answer reviewer."""
import re

WITNESS_POLICY = 'clause-bound-quotation-and-scope/v2-boundary-omission'


def assertion_clauses(assertion):
    """Exact sentence spans; shared verbs and qualifications stay together."""
    # Keep the remaining tail intact after seven boundaries. The mandatory
    # overall judgment also checks relationships across these sentence spans.
    spans = re.split(r'(?<=[.!?])(?=\s+[A-Z])', assertion, maxsplit=7)
    return {f'S{i}': span for i, span in enumerate(spans)}


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
            witness = {'citation_ref': refs['items'],
                'quote': {'type': 'string', 'minLength': 1, 'maxLength': 600},
                'scope_relation': {'type': 'string', 'enum': ['compatible', 'different', 'not_established']}}
            props['witnesses'] = {'type': 'array', 'maxItems': min(8, len(references)),
                'items': {'type': 'object', 'properties': witness,
                    'required': list(witness), 'additionalProperties': False}}
        props.update(citation_refs={**refs, 'minItems': 0},
            reason={'type': 'string', 'maxLength': 600}, verdict={'type': 'string', 'enum': verdicts})
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


def _quotation(text, *, unwrap=False):
    # Soft hyphens and whitespace are PDF layout, not semantic equivalence.
    # Keep ordinary hyphens, punctuation, casing and negation unchanged.
    text = text.replace('\u00ad', '')
    if unwrap:
        # An alternative match permits a word split at an actual PDF newline.
        # Inline compound hyphens are never removed, nor are stored originals.
        text = re.sub(r'(?<=[A-Za-z])-[ \t]*\r?\n[ \t]*(?=[a-z])', '-' if unwrap == 'hyphen' else '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _witness_excerpt(text):
    # Conventional edge omissions describe where a contiguous excerpt ends.
    # Remove at most one marker at each edge of the MODEL quotation only;
    # internal omissions and all original source text remain unchanged.
    text = text.strip()
    for marker in ('...', '…'):
        if text.startswith(marker):
            text = text[len(marker):].lstrip()
            break
    for marker in ('...', '…'):
        if text.endswith(marker):
            text = text[:-len(marker)].rstrip()
            break
    return text


def invalid_clause_witnesses(data, references):
    """A quote must belong to its named original; failure is unavailable review."""
    for clause in data['clauses'].values():
        witnesses = clause['witnesses']
        ids = [witness['citation_ref'] for witness in witnesses]
        if len(ids) != len(set(ids)):
            return 'duplicate_clause_witness'
        if set(ids) != set(clause['citation_refs']):
            return 'missing_clause_witness'
        for witness in witnesses:
            original = references.get(witness['citation_ref'])
            excerpt = _witness_excerpt(witness['quote'])
            quote = _quotation(excerpt)
            if original is None or not quote:
                return 'unbound_clause_witness'
            if (quote not in _quotation(original['quote'])
                    and not any(_quotation(excerpt, unwrap=layout) in _quotation(original['quote'], unwrap=layout)
                        for layout in ('hyphen', 'word'))):
                return 'unbound_clause_witness'
    return None


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
