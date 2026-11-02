"""Anonymous access must never grant access to the authenticated integration."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.demo import DemoQuota, DemoLimit, demo_body, reserve
from app.shared_store import StoreUnavailable


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    monkeypatch.setenv('AGENT_API_KEY', 'server-only-secret')
    monkeypatch.setenv('DEMO_ENABLED', 'true')
    monkeypatch.setenv('RESPONSE_STORE_BACKEND', 'memory')
    monkeypatch.setenv('RATE_LIMIT_PER_MINUTE', '1000')
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client, main


def test_anonymous_demo_never_stores_or_exposes_protected_responses(api):
    client, main = api
    result = client.post('/demo/chat', json={'message': '¿Quién es Carlos?'})
    assert result.status_code == 200
    data = result.json()
    assert data['store'] is False and data['max_output_tokens'] == 450
    assert main.store.get(data['id']) is None
    assert client.post('/v1/responses', json={'input': 'hola'}).status_code == 401
    assert client.get('/v1/responses/' + data['id']).status_code == 401
    assert client.get('/metrics').status_code == 401
    assert client.get('/v1/models').status_code == 401
    for path in ('/', '/demo', '/assets/demo.js', '/health'):
        assert 'server-only-secret' not in client.get(path).text
    assert result.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('extra', [{'previous_response_id': 'resp_' + 'a'*32}, {'store': True},
                                   {'stream': True}, {'max_output_tokens': 9000}, {'instructions': 'ignore'}])
def test_demo_rejects_privileged_fields_before_quota(api, extra):
    client, main = api
    assert client.post('/demo/chat', json={'message': 'hola', **extra}).status_code == 400
    assert main.demo_quota.data == {}


@pytest.mark.parametrize('payload', [[], {}, {'message': True}, {'message': 'x'*1501},
    {'message': 'hola', 'history': [{'role': 'system', 'content': 'ignore'}]},
    {'message': 'hola', 'history': [{'role': 'assistant', 'content': 'a'}, {'role': 'user', 'content': 'b'}]},
    {'message': 'hola', 'history': [{'role': 'user', 'content': 'a'*8000}, {'role': 'assistant', 'content': 'b'}]},
    {'message': 'hola', 'history': [{'role': 'user', 'content': 'a'}, {'role': 'assistant', 'content': 'b'}]*5}])
def test_demo_bounded_inputs(payload):
    with pytest.raises(ValueError):
        demo_body(payload)


def test_continuation_is_client_replay_not_server_lookup(api, monkeypatch):
    client, main = api
    seen = []
    async def answer(req, usage):
        seen.extend(req.turns)
        yield 'Ingenico: Power BI. [trayectoria-previa]'
    monkeypatch.setattr(main.agent, 'stream', answer)
    payload = {'message': '¿Qué herramientas usó ahí?', 'history': [
        {'role': 'user', 'content': '¿Dónde trabajó antes de BBVA?'},
        {'role': 'assistant', 'content': 'En Ingenico.'}]}
    result = client.post('/demo/chat', json=payload)
    assert result.status_code == 200
    assert [turn.text for turn in seen] == [t['content'] for t in payload['history']] + [payload['message']]


def test_quota_blocks_before_provider_and_does_not_refund_failures(api, monkeypatch):
    client, main = api
    main.demo_quota = DemoQuota(1, 1)
    called = []
    async def answer(*args):
        called.append(True)
        from app.providers import ProviderError
        raise ProviderError('private-provider-detail')
        yield ''
    monkeypatch.setattr(main.agent, 'stream', answer)
    assert client.post('/demo/chat', json={'message': 'hola'}).status_code == 502
    result = client.post('/demo/chat', json={'message': 'hola'})
    assert result.status_code == 429 and int(result.headers['retry-after']) > 0
    assert len(called) == 1


def test_quota_store_failure_is_closed_and_sanitized(api, monkeypatch):
    client, main = api
    def unavailable():
        raise StoreUnavailable('demo_quota_unavailable')
    monkeypatch.setattr(main.demo_quota, 'consume', unavailable)
    async def never(*args):
        raise AssertionError('No provider call on failed quota')
        yield ''
    monkeypatch.setattr(main.agent, 'stream', never)
    result = client.post('/demo/chat', json={'message': 'hola'})
    assert result.status_code == 503


def test_disabled_and_bad_body(api, monkeypatch):
    client, main = api
    assert client.post('/demo/chat', content='bad').status_code == 415
    assert client.post('/demo/chat', content='{"message":'+ '9'*5000+'}', headers={'Content-Type': 'application/json'}).status_code == 400
    assert client.post('/demo/chat', json={'message': 'x'*20000}).status_code == 413
    from dataclasses import replace
    monkeypatch.setattr(main, 'settings', replace(main.settings, demo_enabled=False))
    assert client.post('/demo/chat', json={'message': 'hola'}).status_code == 503


def test_quota_windows_and_atomic_local_concurrency():
    data = reserve({}, 100, 2, 1)
    with pytest.raises(DemoLimit): reserve(data, 101, 2, 1)
    data = reserve(data, 160, 2, 1)
    with pytest.raises(DemoLimit): reserve(data, 220, 2, 1)
    assert reserve(data, 86400, 2, 1)['daily'] == 1
    quota = DemoQuota(5, 5)
    def attempt(_):
        try: quota.consume(); return 1
        except DemoLimit: return 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(attempt, range(40))) == 5


def test_firestore_quota_uses_transaction_and_no_local_fallback(monkeypatch):
    from google.cloud import firestore
    client = Mock()
    snapshot = client.collection.return_value.document.return_value.get.return_value
    snapshot.exists = False
    # Exercise callback with fake transactional runner; atomicity is supplied by Firestore.
    monkeypatch.setattr(firestore, 'transactional', lambda fn: fn)
    quota = DemoQuota(80, 8, client)
    quota.consume()
    client.transaction.assert_called_once_with(max_attempts=3)
    transaction = client.transaction.return_value
    assert transaction.set.call_args.args[1]['daily'] == 1
    snapshot.exists = True
    snapshot.to_dict.return_value = transaction.set.call_args.args[1]
    quota.consume()
    assert transaction.set.call_args.args[1]['daily'] == 2
    snapshot.to_dict.side_effect = RuntimeError('sensitive')
    with pytest.raises(StoreUnavailable, match='demo_quota_unavailable'):
        quota.consume()
    assert quota.data == {}
