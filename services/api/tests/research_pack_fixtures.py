"""Build the current atomic pack shape from retained single-point model fixtures."""
import json
from functools import wraps


def witnessed_review(value, payload):
    """Express old scripted verdicts with exact supplied clause witnesses.

    Explicit witness lists are never repaired: boundary tests supply their own
    malformed, mismatched or out-of-scope witnesses to exercise host rejection.
    """
    originals = {passage['citation_ref']: passage['text']
        for field in ('sources', 'source_context') for source in payload.get(field, [])
        for passage in source.get('passages', []) if 'citation_ref' in passage}
    value['clauses'] = {key: {**clause, 'witnesses': clause.get('witnesses', [{'citation_ref': ref,
        'quote': originals.get(ref, 'This test citation is not a supplied original.')[:200],
        'scope_relation': 'compatible'} for ref in clause.get('citation_refs', [])])}
        for key, clause in value.get('clauses', {}).items()}
    return value


def atomic_pack_model(method):
    @wraps(method)
    async def complete(*args, **kwargs):
        raw = await method(*args, **kwargs)
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return raw
        properties = kwargs.get('response_schema', {}).get('properties', {})
        if (isinstance(value, dict) and isinstance(value.get('clauses'), dict)
                and any('witnesses' in clause.get('required', [])
                    for clause in properties.get('clauses', {}).get('properties', {}).values())):
            return json.dumps(witnessed_review(value, json.loads(args[-1])))
        if 'points' not in properties:
            return raw
        if not isinstance(value, dict) or not {'statement', 'evidence', 'remaining_gap'} <= value.keys():
            return raw
        point = {key: value.pop(key) for key in ('statement', 'evidence')}
        return json.dumps({'points': [point] if point['statement'] or point['evidence'] else [], **value})
    return complete
