"""Compatibilidad con clientes Open Responses, tarjeta A2A y observabilidad (proveedor mock, sin red)."""
import importlib
import json
import logging

import pytest
from fastapi.testclient import TestClient

H = {"Authorization": "Bearer test-key"}


@pytest.fixture()
def main(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AGENT_API_KEY", "test-key")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("MAX_HISTORY_TURNS", "2")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    import app.main as m
    importlib.reload(m)
    return m


@pytest.fixture()
def client(main):
    return TestClient(main.app)


def post(client, **body):
    body.setdefault("input", "¿Cuál es tu experiencia actual?")
    return client.post("/v1/responses", headers=H, json=body)


# ---------------------------------------------------------------- parámetros
def test_platform_example_extra_params_are_accepted(client):
    r = post(client, temperature=0.7, reasoning={"effort": "medium"})
    assert r.status_code == 200, r.text
    assert r.json()["temperature"] == 0.7


@pytest.mark.parametrize("extra", [
    {"stream_options": {"include_usage": True}},
    {"include": ["reasoning.encrypted_content"]},
    {"service_tier": "auto"},
    {"prompt_cache_key": "abc"},
    {"safety_identifier": "user-1"},
    {"top_logprobs": 0},
    {"text": {"format": {"type": "text"}, "verbosity": "medium"}},
    {"truncation": "auto"},
])
def test_common_client_defaults_do_not_break_requests(client, extra):
    r = post(client, **extra)
    assert r.status_code == 200, r.text


def test_ignored_params_are_not_echoed_as_applied(client):
    body = post(client, reasoning={"effort": "high"}).json()
    assert body["reasoning"] is None


def test_temperature_above_one_is_capped(client):
    assert post(client, temperature=1.5).json()["temperature"] == 1.0


@pytest.mark.parametrize("extra,param", [
    ({"temperature": 3}, "temperature"),
    ({"tools": [{"type": "function", "name": "x"}]}, "tools"),
    ({"text": {"format": {"type": "json_schema", "name": "x", "schema": {}}}}, "text"),
    ({"background": True}, "background"),
    ({"conversation": "conv_1"}, "conversation"),
])
def test_capabilities_we_do_not_have_are_still_rejected(client, extra, param):
    r = post(client, **extra)
    assert r.status_code == 400
    assert r.json()["error"]["param"] == param


# ---------------------------------------------------------------- historial
def _transcript(pairs: int):
    items = []
    for i in range(pairs):
        items.append({"role": "user", "content": f"pregunta {i}"})
        items.append({"role": "assistant", "content": [{"type": "output_text", "text": f"respuesta {i}"}]})
    items.append({"role": "user", "content": "¿Qué proyectos de IA tienes?"})
    return items


def test_long_transcript_fails_without_truncation(client):
    r = post(client, input=_transcript(6))
    assert r.status_code == 400 and "historial" in r.json()["error"]["message"]


def test_long_transcript_is_trimmed_with_truncation_auto(client, main):
    r = post(client, input=_transcript(6), truncation="auto")
    assert r.status_code == 200, r.text
    assert r.json()["truncation"] == "auto"
    assert main.metrics.flags["history_truncated"] == 1


# ---------------------------------------------------------------- tarjeta A2A
def test_agent_card_is_public_and_points_to_open_responses(client):
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = r.json()
    assert card["url"] == "http://testserver/v1"
    assert card["capabilities"]["streaming"] is True
    ext = card["capabilities"]["extensions"][0]
    assert ext["params"]["endpoint"] == "http://testserver/v1/responses"
    assert card["securitySchemes"]["bearer"]["scheme"] == "bearer"
    assert card["skills"] and card["defaultInputModes"] == ["text/plain"]
    assert "test-key" not in r.text


def test_agent_card_uses_configured_public_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://agente.example.com/")
    import app.main as m
    importlib.reload(m)
    card = TestClient(m.app).get("/.well-known/agent-card.json").json()
    assert card["url"] == "https://agente.example.com/v1"


# ---------------------------------------------------------------- observabilidad
def test_metrics_require_auth(client):
    assert client.get("/metrics").status_code == 401


def test_metrics_count_responses_tokens_and_ignored_params(client):
    post(client)
    post(client, reasoning={"effort": "low"})
    client.post("/v1/responses", headers=H, json={"input": "hola", "stream": True})
    m = client.get("/metrics", headers=H).json()
    assert m["responses"]["completed"] == 3
    assert m["latency_ms"]["samples"] == 3 and m["latency_ms"]["p50"] is not None
    assert m["time_to_first_token_ms"]["samples"] == 1
    assert m["ignored_params"] == {"reasoning": 1}
    assert m["http"]["POST /v1/responses 200"] == 3
    assert m["scope"] == "instance"


def test_request_id_is_generated_or_propagated(client):
    r = client.get("/health")
    assert len(r.headers["X-Request-ID"]) == 16
    r = client.get("/health", headers={"X-Request-ID": "demo-123"})
    assert r.headers["X-Request-ID"] == "demo-123"
    r = client.get("/health", headers={"X-Request-ID": "<script>"})
    assert r.headers["X-Request-ID"] != "<script>"


def test_json_logs_are_cloud_logging_compatible_and_carry_no_content(monkeypatch):
    from app import observability as obs

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    obs.new_request_context({"x-request-id": "rid-1",
                             "x-cloud-trace-context": "0123456789abcdef0123456789abcdef/1;o=1"})
    record = logging.LogRecord("cv-agent", logging.WARNING, __file__, 1, "response", None, None)
    record.fields = {"status": "completed", "input_tokens": 10}
    entry = json.loads(obs.JsonFormatter().format(record))
    assert entry["severity"] == "WARNING"
    assert entry["request_id"] == "rid-1"
    assert entry["logging.googleapis.com/trace"] == "projects/demo-project/traces/0123456789abcdef0123456789abcdef"
    assert entry["input_tokens"] == 10


# ---------------------------------------------------------------- citas
def test_citations_hidden_by_default_and_returned_as_annotations(client):
    part = post(client, input="¿Qué proyectos de IA has construido?").json()["output"][0]["content"][0]
    assert "[proyectos-ia]" not in part["text"] and "[perfil]" not in part["text"]
    assert part["annotations"], "las fuentes deben viajar como annotations"
    a = part["annotations"][0]
    assert a["type"] == "file_citation" and a["file_id"] and a["filename"] and 0 <= a["index"] <= len(part["text"])


def test_client_can_ask_for_inline_citations(client):
    part = post(client, input="¿Qué proyectos de IA has construido?",
                metadata={"citations": "inline"}).json()["output"][0]["content"][0]
    first = part["annotations"][0]
    assert part["text"][first["index"]:].startswith(f"[{first['file_id']}]")


def test_invalid_citation_preference_is_rejected(client):
    r = post(client, metadata={"citations": "footnotes"})
    assert r.status_code == 400 and r.json()["error"]["param"] == "metadata"
