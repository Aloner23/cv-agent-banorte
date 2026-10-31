"""Fallos de red simulados, límites y almacenamiento: ninguna llamada al proveedor."""
import asyncio
import importlib
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.agent import Turn
from app.config import Settings
from app.openresponses import ResponseStore
from app.providers import ProviderError


H = {"Authorization": "Bearer test-key"}


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AGENT_API_KEY", "test-key")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client, main


def events(raw):
    return [json.loads(line[6:]) for line in raw.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"]


@pytest.mark.parametrize('stream', [False, True])
def test_upstream_quota_is_distinct_and_never_reported_completed(api, monkeypatch, stream):
    client, main = api

    async def limited(*args, **kwargs):
        raise ProviderError('private-secret', 'provider_rate_limit', retry_after=37)
        yield ''

    monkeypatch.setattr(main.agent, 'stream', limited)
    response = client.post('/v1/responses', json={'input': 'hola', 'stream': stream}, headers=H)
    assert 'private-secret' not in response.text
    if stream:
        payloads = events(response.text)
        failed = next(p for p in payloads if p['type'] == 'response.failed')
        assert failed['response']['error']['code'] == 'provider_rate_limit'
        assert not any(p['type'] == 'response.completed' for p in payloads)
        assert response.text.endswith('data: [DONE]\n\n')
    else:
        assert response.status_code == 503 and response.headers['Retry-After'] == '37'
        assert response.json()['error']['code'] == 'provider_rate_limit'


@pytest.mark.parametrize("payload,param", [
    ({"input": "hola", "previous_response_id": []}, "previous_response_id"),
    ({"input": "hola", "instructions": {}}, "instructions"),
    ({"input": "hola", "stream": "false"}, "stream"),
    ({"input": "hola", "store": 1}, "store"),
    ({"input": "hola", "max_output_tokens": True}, "max_output_tokens"),
    ({"input": "hola", "max_output_tokens": -1}, "max_output_tokens"),
    ({"input": "hola", "max_output_tokens": 1.5}, "max_output_tokens"),
    ({"input": "hola", "temperature": False}, "temperature"),
    ({"input": "hola", "temperature": 2.5}, "temperature"),
    ({"input": "hola", "temperature": 10 ** 1000}, "temperature"),
    ({"input": "hola", "top_p": True}, "top_p"),
    ({"input": "hola", "truncation": "smart"}, "truncation"),
    ({"input": "hola", "metadata": {"bad": []}}, "metadata"),
    ({"input": "hola", "background": True}, "background"),
    ({"input": "hola", "tools": [{"type": "function", "name": "foo"}]}, "tools"),
    ({"input": "hola", "text": {"format": {"type": "json_object"}}}, "text"),
    ({"input": [{"role": "user", "content": [{"type": "input_text", "text": 1}]}]}, "input"),
    ({"input": [{"role": "user", "content": [{"type": "input_image", "image_url": "x"}]}]}, "input"),
    ({"input": [{"type": "function_call_output", "call_id": "x", "output": "ok"}]}, "input"),
    ({"input": [{"role": "tool", "content": "x"}]}, "input"),
])
def test_malformed_or_unsupported_payloads_are_400(api, payload, param):
    client, _ = api
    response = client.post("/v1/responses", json=payload, headers=H)
    assert response.status_code == 400
    assert response.json()["error"]["param"] == param


def test_request_size_and_json_encoding(api):
    client, main = api
    assert client.post("/v1/responses", json={"input": "x" * main.settings.max_request_bytes}, headers=H).status_code == 413
    headers = {**H, "Content-Type": "application/json"}
    assert client.post("/v1/responses", content=b'\xff', headers=headers).status_code == 400
    assert client.post("/v1/responses", content='{"input":"x","temperature":NaN}', headers=headers).status_code == 400
    assert client.post("/v1/responses", content='{}', headers=H).status_code == 415


def test_effective_model_and_generation_limits(api):
    client, main = api
    unknown = client.post("/v1/responses", json={"input": "hola", "model": "nonexistent"}, headers=H)
    assert unknown.status_code == 400 and unknown.json()["error"]["code"] == "model_not_found"
    response = client.post("/v1/responses", json={"input": "experiencia", "max_output_tokens": 99999}, headers=H)
    assert response.json()["max_output_tokens"] == main.settings.max_output_tokens


def test_mock_is_live_but_not_ready(api):
    client, _ = api
    state = client.get("/health").json()
    assert state["status"] == "ok" and state["ready"] is False
    assert state["readiness_reasons"] == ["demo_mode"]
    assert state["readiness_check"] == "local_configuration_only"
    assert client.get("/ready").status_code == 503


def test_missing_provider_credentials_does_not_call_provider(api, monkeypatch):
    client, main = api
    monkeypatch.setattr(main.agent, "provider_name", "gemini")
    monkeypatch.setattr(main, "settings", replace(main.settings, gemini_api_key=""))
    assert client.get("/ready").status_code == 503
    response = client.post("/v1/responses", json={"input": "hola"}, headers=H)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "agent_not_ready"


def test_default_provider_remains_gemini_without_its_credentials(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-other-provider-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-other-provider-key")
    settings = Settings()
    assert settings.resolved_provider() == "gemini"
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as client:
        state = client.get("/ready")
        assert state.status_code == 503
        assert state.json()["provider"] == "gemini"
        assert state.json()["readiness_reasons"] == ["provider_credentials_missing"]


@pytest.mark.parametrize("stream", [False, True])
def test_provider_failures_are_terminal_and_sanitized(api, monkeypatch, stream):
    client, main = api

    async def fail(req, usage):
        yield "Respuesta parcial."
        raise ProviderError("super-secret upstream error body")

    monkeypatch.setattr(main.agent, "stream", fail)
    response = client.post("/v1/responses", json={"input": "hola", "stream": stream}, headers=H)
    assert "super-secret" not in response.text
    if not stream:
        assert response.status_code == 502
    else:
        data = events(response.text)
        assert [e["type"] for e in data[-2:]] == ["error", "response.failed"]
        assert data[-1]["response"]["status"] == "failed"
        assert "response.completed" not in response.text
        assert response.text.count("data: [DONE]") == 1
        assert client.get("/v1/responses/" + data[-1]["response"]["id"], headers=H).status_code == 404


@pytest.mark.parametrize("stream", [False, True])
def test_timeout_has_a_terminal_error(api, monkeypatch, stream):
    client, main = api
    monkeypatch.setattr(main, "settings", replace(main.settings, request_timeout_seconds=0.01))

    async def delayed(req, usage):
        await asyncio.sleep(1)
        yield "late"

    monkeypatch.setattr(main.agent, "stream", delayed)
    response = client.post("/v1/responses", json={"input": "hola", "stream": stream}, headers=H)
    if stream:
        data = events(response.text)
        assert data[-1]["type"] == "response.failed"
        assert data[-1]["response"]["error"]["code"] == "gateway_timeout"
    else:
        assert response.status_code == 504


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("output", ["Respuesta cortada", ""])
def test_token_truncation_is_incomplete(api, monkeypatch, stream, output):
    client, main = api

    async def truncated(req, usage):
        usage.update(input_tokens=20, output_tokens=5, reasoning_tokens=2, finish_reason="max_output_tokens")
        if output:
            yield output

    monkeypatch.setattr(main.agent, "stream", truncated)
    response = client.post("/v1/responses", json={"input": "hola", "stream": stream}, headers=H)
    if stream:
        data = events(response.text)
        assert data[-1]["type"] == "response.incomplete"
        final = data[-1]["response"]
    else:
        final = response.json()
    assert final["status"] == "incomplete"
    assert final["incomplete_details"] == {"reason": "max_output_tokens"}
    assert final["output"][0]["status"] == "incomplete"
    assert final["usage"]["output_tokens_details"]["reasoning_tokens"] == 2


def test_store_false_and_auth_for_reading(api):
    client, _ = api
    response = client.post("/v1/responses", json={"input": "hola", "store": False}, headers=H).json()
    path = "/v1/responses/" + response["id"]
    assert client.get(path, headers=H).status_code == 404
    assert client.get(path).status_code == 401
    followup = client.post("/v1/responses", json={"input": "más", "previous_response_id": response["id"]}, headers=H)
    assert followup.status_code == 404


def test_rate_limit_cannot_be_bypassed_with_forwarded_header(api, monkeypatch):
    client, main = api
    monkeypatch.setattr(main, "settings", replace(main.settings, rate_limit_per_minute=1))
    assert client.post("/v1/responses", json={"input": "hola"}, headers={**H, "X-Forwarded-For": "1.1.1.1"}).status_code == 200
    blocked = client.post("/v1/responses", json={"input": "hola"}, headers={**H, "X-Forwarded-For": "2.2.2.2"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0


def test_cors_and_basic_security_headers(api):
    client, _ = api
    response = client.get("/", headers={"Origin": "https://untrusted.invalid"})
    assert "access-control-allow-origin" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_store_lru_and_ttl(monkeypatch):
    import app.openresponses as protocol
    clock = [100.0]
    monkeypatch.setattr(protocol.time, "monotonic", lambda: clock[0])
    store = ResponseStore(max_items=2, ttl_s=10)
    turns = [Turn("user", "hola")]
    store.put("a", turns, {"id": "a"})
    store.put("b", turns, {"id": "b"})
    assert store.get("a")
    store.put("c", turns, {"id": "c"})
    assert store.get("b") is None and store.get("a")
    clock[0] = 111.0
    store.put("d", turns, {"id": "d"})
    assert list(store.data) == ["d"]


@pytest.mark.parametrize('stream', [False, True])
def test_failed_persistence_is_not_reported_as_completed(api, monkeypatch, stream):
    from app.shared_store import StoreUnavailable
    client, main = api
    def unavailable(*args):
        raise StoreUnavailable('private-store-detail')
    monkeypatch.setattr(main.store, 'put', unavailable)
    r = client.post('/v1/responses', headers=H, json={'input': 'hola', 'stream': stream})
    assert 'private-store-detail' not in r.text
    if stream:
        payloads = events(r.text)
        assert any(p['type'] == 'response.failed' and p['response']['error']['code'] == 'store_unavailable' for p in payloads)
        assert not any(p['type'] == 'response.completed' for p in payloads)
    else:
        assert r.status_code == 503
        assert r.json()['error']['code'] == 'store_unavailable'
    r = client.post('/v1/responses', headers=H, json={'input': 'hola', 'store': False})
    assert r.status_code == 200  # Sin persistencia no depende del almacén.


def test_history_backend_failure_returns_503(api, monkeypatch):
    from app.shared_store import StoreUnavailable
    client, main = api
    def unavailable(*args):
        raise StoreUnavailable('private-store-detail')
    monkeypatch.setattr(main.store, 'get', unavailable)
    r = client.post('/v1/responses', headers=H, json={'input': 'continúa', 'previous_response_id': 'resp_' + 'a'*32})
    assert r.status_code == 503
    assert r.json()['error']['code'] == 'store_unavailable'
