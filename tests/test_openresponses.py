"""Pruebas de contrato Open Responses + guardrails (sin red: proveedor mock)."""
import importlib
import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AGENT_API_KEY", "test-key")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app)


H = {"Authorization": "Bearer test-key"}
REQUIRED = {"id", "object", "created_at", "status", "model", "output", "tools", "tool_choice", "truncation",
            "parallel_tool_calls", "text", "top_p", "temperature", "usage", "store", "background", "metadata",
            "error", "incomplete_details", "previous_response_id", "instructions"}


def parse_sse(raw: str):
    events = []
    for block in raw.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.split("\n") if ": " in l)
        if lines.get("data") == "[DONE]" or "data" not in lines:
            continue
        ev = json.loads(lines["data"])
        assert lines["event"] == ev["type"], "event: debe coincidir con type"
        events.append(ev)
    return events


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["documents"] >= 5


def test_auth_required(client):
    assert client.post("/v1/responses", json={"input": "hola"}).status_code == 401
    assert client.post("/v1/responses", json={"input": "hola"}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_non_streaming_shape(client):
    r = client.post("/v1/responses", json={"model": "carlos-cv-agent", "input": "¿Dónde estudió Carlos?"}, headers=H)
    assert r.status_code == 200
    body = r.json()
    assert REQUIRED <= body.keys()
    assert body["object"] == "response" and body["status"] == "completed"
    msg = body["output"][0]
    assert msg["type"] == "message" and msg["role"] == "assistant" and msg["status"] == "completed"
    assert msg["content"][0]["type"] == "output_text" and "ITAM" in msg["content"][0]["text"]
    assert body["usage"]["total_tokens"] == body["usage"]["input_tokens"] + body["usage"]["output_tokens"]


def test_input_as_item_list(client):
    payload = {"input": [
        {"type": "message", "role": "system", "content": "Responde breve"},
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "¿Qué idiomas habla?"}]},
    ]}
    r = client.post("/v1/responses", json=payload, headers=H)
    assert r.status_code == 200
    assert "Inglés" in r.json()["output_text"] or "inglés" in r.json()["output_text"].lower()


def test_streaming_event_order(client):
    with client.stream("POST", "/v1/responses", json={"input": "proyectos de IA", "stream": True}, headers=H) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        raw = "".join(r.iter_text())
    evs = parse_sse(raw)
    types = [e["type"] for e in evs]
    assert types[:4] == ["response.created", "response.in_progress", "response.output_item.added", "response.content_part.added"]
    assert types[-4:] == ["response.output_text.done", "response.content_part.done", "response.output_item.done", "response.completed"]
    assert all(t == "response.output_text.delta" for t in types[4:-4]) and len(types) > 8
    seqs = [e["sequence_number"] for e in evs]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    deltas = "".join(e["delta"] for e in evs if e["type"] == "response.output_text.delta")
    done = next(e for e in evs if e["type"] == "response.output_text.done")
    assert deltas == done["text"] == evs[-1]["response"]["output"][0]["content"][0]["text"]
    assert data_dones(raw) == 1


def data_dones(raw):
    return raw.count("data: [DONE]")


def test_previous_response_id_multiturn(client):
    r1 = client.post("/v1/responses", json={"input": "¿Dónde trabaja?"}, headers=H).json()
    r2 = client.post("/v1/responses", json={"input": "¿Y antes?", "previous_response_id": r1["id"]}, headers=H)
    assert r2.status_code == 200 and r2.json()["previous_response_id"] == r1["id"]
    assert client.get(f"/v1/responses/{r1['id']}", headers=H).status_code == 200


def test_unknown_previous_id(client):
    r = client.post("/v1/responses", json={"input": "x", "previous_response_id": "resp_nope"}, headers=H)
    assert r.status_code == 404 and r.json()["error"]["param"] == "previous_response_id"


@pytest.mark.parametrize("payload", [{}, {"input": 5}, {"input": ""}, {"input": [{"role": "assistant", "content": "hola"}]}])
def test_bad_requests(client, payload):
    r = client.post("/v1/responses", json=payload, headers=H)
    assert r.status_code == 400 and "error" in r.json()


def test_input_too_long(client):
    r = client.post("/v1/responses", json={"input": "a" * 10000}, headers=H)
    assert r.status_code == 400


def test_phone_redaction():
    from app.agent import CVAgent
    assert "0000" not in CVAgent.redact("Llámale al +52 000 000 0000 cuando puedas")


def test_retrieval_finds_right_sections():
    from pathlib import Path
    from app.knowledge import KnowledgeBase
    kb = KnowledgeBase(Path(__file__).parent.parent / "knowledge")
    cases = {
        "¿Qué estudió y en qué universidad?": "formacion-habilidades",
        "Generador de cartas PGMM ahorro": "proyectos-ia",
        "experiencia en Ingenico": "trayectoria-previa",
        "premios BBVA Innova": "liderazgo-reconocimientos",
        "¿cuántos colaboradores ha capacitado como IA Wizard?": "bbva-actual",
    }
    for q, expected in cases.items():
        top = [c.doc_id for c, _ in kb.index.search(q, k=3)]
        assert expected in top, (q, top)
