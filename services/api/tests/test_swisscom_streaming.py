"""Complete-response streaming through fake HTTP streams; no live inference."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from test_model_completion_status import settings
from test_settings import transport

from helvetic_lens import research_gateway
from helvetic_lens.analysis import InferenceBudget, ModelClient
from helvetic_lens.config import DomainError
from helvetic_lens.product_iterative_research import ResearchPlan


def frame(content=None, *, finish=None, **delta):
    if content is not None:
        delta['content'] = content
    return {'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}


def event(value):
    return ('data: ' + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)) + '\r\n\r\n').encode()


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, *, failure=None, delay=0):
        self.chunks, self.failure, self.delay = chunks, failure, delay
        self.closed, self.started = False, asyncio.Event()
        self.delivered = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            await asyncio.sleep(self.delay)
            self.started.set()
            self.delivered += 1
            yield chunk
        if self.failure:
            raise self.failure

    async def aclose(self):
        self.closed = True


def streamed(chunks, **options):
    stream = chunks if isinstance(chunks, Chunks) else Chunks(chunks)
    return httpx.Response(200, headers={'content-type': 'text/event-stream; charset=utf-8'}, stream=stream, **options)


@pytest.mark.asyncio
async def test_fragmented_stream_preserves_schema_allowance_usage_and_only_content(tmp_path, monkeypatch):
    text = '{"answer":"Це école 🏔️"}'
    usage = {'prompt_tokens': 67, 'completion_tokens': 14, 'total_tokens': 81}
    raw = b': heartbeat\r\n\r\n' + event(frame(role='assistant', reasoning_content='PRIVATE REASONING'))
    raw += event(frame(text[:12])) + event(frame(text[12:])) + event(frame(finish='stop'))
    raw += event({'choices': [], 'usage': usage}) + event('[DONE]')
    stream = Chunks([raw[index:index + 3] for index in range(0, len(raw), 3)])
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return streamed(stream)

    transport(monkeypatch, respond)
    configured = settings(tmp_path, 'swisscom')
    model, budget = ModelClient(configured), InferenceBudget(3)
    schema = {'type': 'object', 'properties': {'answer': {'type': 'string'}},
        'required': ['answer'], 'additionalProperties': False}
    token = model.begin_trace()
    result = await model.complete('Original system.', 'Original source.', response_schema=schema,
        budget=budget, max_output_tokens=256)
    trace = model.end_trace(token)
    assert result == text and stream.closed and len(calls) == budget.used == 1
    body = calls[0]
    assert body['stream'] is True and body['stream_options'] == {'include_usage': True}
    assert body['model'] == configured.apertus_model and body['max_tokens'] == 256
    assert body['messages'] == [{'role': 'system', 'content': 'Original system.'},
        {'role': 'user', 'content': 'Original source.'}]
    assert body['response_format']['json_schema'] == {'name': 'structured_response', 'strict': True, 'schema': schema}
    assert trace[-1]['usage'] == usage and trace[-1]['outcome'] == 'success'
    assert 'PRIVATE REASONING' not in json.dumps(trace)


@pytest.mark.asyncio
async def test_multiline_data_usage_totals_and_eof_done_marker(tmp_path, monkeypatch):
    # SSE permits multiple data lines and a last event without a blank delimiter.
    raw = b'event: completion\ndata: {"choices":\ndata: [{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'
    raw += event({'choices': [], 'usage': {'total_tokens': 4}})
    raw += event({'choices': [], 'usage': {'total_tokens': 6}}) + b'data: [DONE]'
    transport(monkeypatch, lambda request: streamed([raw]))
    model = ModelClient(settings(tmp_path, 'swisscom'))
    token = model.begin_trace()
    assert await model.complete('system', 'input') == 'ok'
    assert model.end_trace(token)[-1]['usage'] == {'total_tokens': 6}


@pytest.mark.asyncio
@pytest.mark.parametrize(('tail', 'finish_reason', 'rejection_reason'), [
    ([], None, 'eof'), ([frame(finish='stop')], 'stop', 'eof'),
    (['[DONE]'], None, 'done_before_stop'),
    ([frame(finish='length'), '[DONE]'], 'length', 'non_stop_finish'),
    ([frame(finish='content_filter'), '[DONE]'], 'content_filter', 'non_stop_finish'),
    ([frame(finish='tool_calls'), '[DONE]'], 'tool_calls', 'non_stop_finish'),
    ([frame(finish='function_call'), '[DONE]'], 'function_call', 'non_stop_finish'),
    ([frame(finish='PRIVATE PROVIDER REASON'), '[DONE]'], 'other', 'non_stop_finish'),
    ([frame(finish={'private': 'PRIVATE PROVIDER REASON'}), '[DONE]'], 'other', 'non_stop_finish'),
    ([frame(refusal='PRIVATE REFUSAL', finish='stop'), '[DONE]'], 'stop', 'refusal'),
    ([frame(tool_calls=[{'id': 'PRIVATE TOOL'}]), '[DONE]'], None, 'tool_call'),
    ([frame(function_call={'name': 'PRIVATE TOOL'}), '[DONE]'], None, 'tool_call'),
])
async def test_unfinished_or_refused_stream_never_returns_parseable_partial_text(
        tmp_path, monkeypatch, tail, finish_reason, rejection_reason):
    stream = Chunks([event(frame('{"syntactically":"complete but PRIVATE"}'))] + [event(value) for value in tail])
    transport(monkeypatch, lambda request: streamed(stream))
    model, budget = ModelClient(settings(tmp_path, 'swisscom')), InferenceBudget(3)
    responses = []
    monkeypatch.setattr(model, 'log_exchange', lambda **values: responses.append(values['response_body_override']))
    token = model.begin_trace()
    with pytest.raises(DomainError) as error:
        await model.complete('system', 'input', budget=budget)
    assert error.value.code == 'model_incomplete' and 'PRIVATE' not in error.value.message
    assert budget.used == 1 and stream.closed
    assert model.end_trace(token)[-1]['error_code'] == 'model_incomplete'
    receipt = responses[-1]['stream']
    assert receipt['finish_reason'] == finish_reason and receipt['rejection_reason'] == rejection_reason
    assert 'PRIVATE' not in json.dumps(responses), 'Error metadata must not retain provider text or partial output'


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [
    '{malformed', {'error': {'message': 'PRIVATE PROVIDER ERROR'}},
    {'choices': [{'index': 1, 'delta': {'content': 'private'}, 'finish_reason': 'stop'}]},
    {'choices': [frame()['choices'][0], frame()['choices'][0]]},
    frame(['invalid text block']), {'choices': [], 'usage': 'PRIVATE INVALID USAGE'},
])
async def test_malformed_stream_uses_existing_bounded_error_path_without_partial_text(tmp_path, monkeypatch, bad):
    transport(monkeypatch, lambda request: streamed([event(frame('PRIVATE PARTIAL')), event(bad), event('[DONE]')]))
    budget = InferenceBudget(1)
    with pytest.raises(DomainError) as error:
        await ModelClient(settings(tmp_path, 'swisscom')).complete('system', 'input', budget=budget)
    assert error.value.code == 'model_error' and 'PRIVATE' not in error.value.message and budget.used == 1


@pytest.mark.asyncio
async def test_interrupted_stream_does_not_enter_gateway_format_repair(tmp_path, monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return streamed([event(frame('{"branches":[],"private":"UNFINISHED PLAN"}'))])

    transport(monkeypatch, respond)
    configured = settings(tmp_path, 'swisscom')
    service = SimpleNamespace(settings=configured, model_client=ModelClient(configured))
    work = {'phase': 'plan', 'unmetered_research': True,
        'input': {'question': 'Find the relevant source records.', 'sources': []}}
    with pytest.raises(DomainError) as error:
        await research_gateway.complete(service, work, 'Return an operational plan.', ResearchPlan, 30)
    assert error.value.code == 'model_incomplete' and len(calls) == work['model_route']['model_requests'] == 1
    assert not work['model_route'].get('format_repair') and 'UNFINISHED PLAN' not in json.dumps(work)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 504])
async def test_pre_stream_http_failure_preserves_backoff_attempt_budget_and_error(tmp_path, monkeypatch, status):
    calls, pauses = [], []

    async def pause(seconds):
        pauses.append(seconds)

    def respond(request):
        calls.append(request)
        return httpx.Response(status, headers={'retry-after': '3'}, json={'error': 'PRIVATE PROVIDER ERROR'})

    transport(monkeypatch, respond)
    monkeypatch.setattr(asyncio, 'sleep', pause)
    budget = InferenceBudget(2)
    with pytest.raises(DomainError) as error:
        await ModelClient(settings(tmp_path, 'swisscom')).complete('system', 'input', budget=budget)
    assert error.value.code == {429: 'model_rate_limited', 504: 'model_upstream_timeout'}[status]
    assert len(calls) == budget.used == 2 and pauses == [3]
    assert 'PRIVATE' not in error.value.message


@pytest.mark.asyncio
async def test_disconnect_retry_has_a_fresh_buffer_and_one_charge_per_attempt(tmp_path, monkeypatch):
    first = Chunks([event(frame('DO NOT REUSE '))], failure=httpx.ReadError('PRIVATE connection detail'))
    second = Chunks([event(frame('Complete.', finish='stop')), event('[DONE]')])
    remaining = iter([first, second])
    transport(monkeypatch, lambda request: streamed(next(remaining)))
    pauses = []

    async def pause(seconds):
        pauses.append(seconds)

    monkeypatch.setattr(asyncio, 'sleep', pause)
    budget = InferenceBudget(2)
    assert await ModelClient(settings(tmp_path, 'swisscom')).complete('system', 'input', budget=budget) == 'Complete.'
    assert budget.used == 2 and first.closed and second.closed and 1.0 in pauses


@pytest.mark.asyncio
async def test_trickling_stream_still_obeys_total_request_deadline(tmp_path, monkeypatch):
    stream = Chunks([event(frame('private'))] * 100, delay=.01)
    transport(monkeypatch, lambda request: streamed(stream))
    budget = InferenceBudget(1, max_seconds=.08)
    with pytest.raises(DomainError) as error:
        await ModelClient(settings(tmp_path, 'swisscom')).complete('system', 'input', budget=budget)
    assert error.value.code == 'model_timeout' and budget.used == 1
    assert stream.closed and 0 < stream.delivered < 100


@pytest.mark.asyncio
async def test_outer_cancellation_closes_stream_without_retry_or_result(tmp_path, monkeypatch):
    stream = Chunks([event(frame('private'))] * 100, delay=.01)
    transport(monkeypatch, lambda request: streamed(stream))
    budget = InferenceBudget(3)
    task = asyncio.create_task(ModelClient(settings(tmp_path, 'swisscom')).complete('system', 'input', budget=budget))
    await stream.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed and budget.used == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['swisscom', 'custom'])
async def test_ordinary_json_response_keeps_legacy_compatibility(tmp_path, monkeypatch, provider):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Complete legacy response.'}}]})

    transport(monkeypatch, respond)
    assert await ModelClient(settings(tmp_path, provider)).complete('system', 'input') == 'Complete legacy response.'
    assert calls[0]['stream'] is (provider == 'swisscom')
    assert ('stream_options' in calls[0]) is (provider == 'swisscom')


@pytest.mark.asyncio
@pytest.mark.parametrize('failed_transport', ['stream', 'stream_non_stop', 'json'])
async def test_stream_logs_keep_usage_and_redaction_but_never_reasoning_or_failed_partial(
        harness, tmp_path, monkeypatch, failed_transport):
    client, _, service, _ = harness
    configured = settings(tmp_path, 'swisscom')
    secret = configured.apertus_api_key.get_secret_value()
    success = [event(frame(reasoning_content='PRIVATE REASONING', thinking='PRIVATE THINKING')),
        event(frame('Complete ' + secret, finish='stop')), event({'choices': [], 'usage': {'total_tokens': 9}}), event('[DONE]')]
    if failed_transport == 'json':
        failed = httpx.Response(200, json={'choices': [
            {'finish_reason': 'length', 'message': {'content': 'PRIVATE UNFINISHED TEXT'}}]})
    else:
        tail = [event(frame(finish='PRIVATE PROVIDER REASON'))] if failed_transport == 'stream_non_stop' else []
        failed = streamed([event(frame('PRIVATE UNFINISHED TEXT')), *tail])
    responses = iter([streamed(success), failed])
    transport(monkeypatch, lambda request: next(responses))
    model = ModelClient(configured, service.integration_logger)
    assert await model.complete('system', 'input') == 'Complete ' + secret
    with pytest.raises(DomainError, match='did not finish'):
        await model.complete('system', 'input')
    rows = client.get('/api/integration-logs').json()['items']
    logs = [client.get('/api/integration-logs/' + row['id']).json() for row in rows]
    rendered = json.dumps(logs)
    assert all(private not in rendered for private in [secret, 'PRIVATE REASONING', 'PRIVATE THINKING',
        'PRIVATE UNFINISHED TEXT', 'PRIVATE PROVIDER REASON'])
    success_log = next(row for row in logs if row['status'] == 'success')
    assert success_log['response_body']['completion']['usage'] == {'total_tokens': 9}
    assert success_log['response_body']['completion']['choices'][0]['message']['content'] == 'Complete [REDACTED]'
    error_log = next(row for row in logs if row['status'] == 'error')
    expected = {} if failed_transport == 'json' else {
        'events': 2 if failed_transport == 'stream_non_stop' else 1,
        'content_characters': 23, 'finished': False, 'done': False,
        'finish_reason': 'other' if failed_transport == 'stream_non_stop' else None,
        'rejection_reason': 'non_stop_finish' if failed_transport == 'stream_non_stop' else 'eof'}
    assert error_log['response_body']['stream'] == expected
