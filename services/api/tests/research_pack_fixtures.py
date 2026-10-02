"""Build the current atomic pack shape from retained single-point model fixtures."""
import json
from functools import wraps


def atomic_pack_model(method):
    @wraps(method)
    async def complete(*args, **kwargs):
        raw = await method(*args, **kwargs)
        if 'points' not in kwargs.get('response_schema', {}).get('properties', {}):
            return raw
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return raw
        if not isinstance(value, dict) or not {'statement', 'evidence', 'remaining_gap'} <= value.keys():
            return raw
        point = {key: value.pop(key) for key in ('statement', 'evidence')}
        return json.dumps({'points': [point] if point['statement'] or point['evidence'] else [], **value})
    return complete
