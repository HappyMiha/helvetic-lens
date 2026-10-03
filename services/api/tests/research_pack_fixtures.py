"""Build the current atomic pack shape from retained single-point model fixtures."""
import json
from functools import wraps


def witnessed_review(value, payload):
    """Express old scripted verdicts using the supplied canonical choices.

    Explicit witness lists are never repaired: boundary tests supply their own
    malformed, mismatched or out-of-scope witnesses to exercise host rejection.
    """
    choices = {passage['citation_ref']: passage['witness_key']
        for field in ('sources', 'source_context') for source in payload.get(field, [])
        for passage in source.get('passages', []) if 'witness_key' in passage}
    value['clauses'] = {key: dict(clause) if 'witnesses' in clause else {
        **{name: item for name, item in clause.items() if name != 'citation_refs'},
        'witnesses': [{'key': choices.get(ref, 'This test reference is not a supplied choice.'),
            'scope_relation': 'compatible'} for ref in clause.get('citation_refs', [])]}
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
