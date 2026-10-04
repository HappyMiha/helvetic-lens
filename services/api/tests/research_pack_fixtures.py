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
    if isinstance(value.get('overall'), dict):
        # Legacy scripts repeat clause citations here. The current host derives
        # that union; preserve the independent verdict, reason and scope.
        value['overall'] = {key: item for key, item in value['overall'].items() if key != 'citation_refs'}
    if 'gap_status' in value and 'gap_resolution' not in value:
        # Legacy scripted answered fixtures identify the statements they meant
        # to answer with. Explicit current resolutions remain untouched, including
        # intentionally empty/invalid choices in rejection tests.
        status = value['gap_status']
        if status != 'answered' and 'answer_point_ids' in value and value['answer_point_ids'] != []:
            return value  # Do not repair an explicitly inconsistent legacy fixture.
        value.pop('gap_status')
        selected = value.pop('answer_point_ids', [item['point_id'] for item in payload.get('delivered_points', [])])
        value['gap_resolution'] = selected if status == 'answered' else status
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
        if not isinstance(value, dict) or not {'statement', 'evidence', 'remaining_gap'} <= value.keys():
            return raw
        # Translate only legacy flat scripted answers. Explicit current-shaped
        # points responses and nonempty forbidden gaps remain validation tests.
        if 'remaining_gap' not in properties and value['remaining_gap'] == '':
            value.pop('remaining_gap')
        if 'points' not in properties:
            if 'statement' not in properties:
                value.pop('statement')
            return json.dumps(value)
        point = {key: value.pop(key) for key in ('statement', 'evidence')}
        points = [point] if point['statement'] or point['evidence'] else []
        if 'statement' not in properties['points']['items']['properties']:
            point.pop('statement')
        return json.dumps({'points': points, **value})
    return complete
