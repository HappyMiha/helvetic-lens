"""Assemble one complete OpenAI-compatible SSE response without exposing deltas."""
import json

from .config import DomainError


async def completion_envelope(response, progress):
    """Return a complete envelope, or fail without returning accumulated text.

    The caller owns HTTP status handling, attempt accounting and total deadline.
    An endpoint which returns ordinary JSON keeps its existing completion checks.
    """
    if response.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'text/event-stream':
        await response.aread()
        return response.json()
    parts, data_lines, usage = [], [], {}
    finished = False
    progress.update(events=0, content_characters=0, finished=False, done=False, finish_reason=None)

    def incomplete(reason):
        progress['rejection_reason'] = reason
        return DomainError('The model stream did not finish a complete answer. Check the output limit or model access.',
            502, 'model_incomplete')

    def consume(data):
        nonlocal finished, usage
        if data == '[DONE]':
            if not finished:
                raise incomplete('done_before_stop')
            progress['done'] = True
            return True
        value = json.loads(data)
        if not isinstance(value, dict) or value.get('error'):
            raise ValueError('Invalid model stream event')
        progress['events'] += 1
        if value.get('usage') is not None:
            if not isinstance(value['usage'], dict):
                raise ValueError('Invalid model stream usage')
            usage = value['usage']  # A trailer is a total, never another amount to sum.
            progress['usage'] = usage
        choices = value.get('choices', [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise ValueError('Invalid model stream choices')
        if not choices:
            return False  # Usage-only trailer or protocol metadata.
        choice = choices[0]
        if (not isinstance(choice, dict) or type(choice.get('index')) is not int
                or choice['index'] != 0 or finished):
            raise ValueError('Invalid model stream choice')
        delta = choice.get('delta')
        if not isinstance(delta, dict):
            raise ValueError('Invalid model stream delta')
        reason = choice.get('finish_reason')
        # Provider values may contain arbitrary text. Keep only finite protocol
        # labels, including when a refusal/tool delta rejects this same frame.
        progress['finish_reason'] = (None if reason is None else reason if isinstance(reason, str)
            and reason in {'stop', 'length', 'content_filter', 'tool_calls', 'function_call'} else 'other')
        if delta.get('refusal'):
            raise incomplete('refusal')
        if delta.get('tool_calls') or delta.get('function_call'):
            raise incomplete('tool_call')
        content = delta.get('content')
        if content is not None:
            if not isinstance(content, str):
                raise ValueError('Invalid model stream content')
            parts.append(content)
            progress['content_characters'] += len(content)
        if reason is not None:
            if reason != 'stop':
                raise incomplete('non_stop_finish')
            finished = True
            progress['finished'] = True
        return False

    async for line in response.aiter_lines():
        if not line:
            if data_lines and consume('\n'.join(data_lines)):
                break
            data_lines.clear()
        elif not line.startswith(':'):
            field, _, value = line.partition(':')
            if field == 'data':
                data_lines.append(value[1:] if value.startswith(' ') else value)
    else:
        if data_lines:
            consume('\n'.join(data_lines))
    if not progress['done']:
        raise incomplete('eof')
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': ''.join(parts)}}], 'usage': usage}
