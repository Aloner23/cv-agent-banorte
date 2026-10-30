"""Contrato Gemini con HTTP simulado: sin claves reales y sin red."""
import asyncio
import json

import httpx
import pytest

from app.agent import Turn
from app.providers import GeminiProvider, ProviderError, _sse_lines


def sse(*events):
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def candidate(text="Carlos trabaja en BBVA.", finish="STOP"):
    value = {"content": {"parts": [{"text": text}]}}
    if finish:
        value["finishReason"] = finish
    return {"candidates": [value]}


async def collect(provider, usage=None):
    return "".join([part async for part in provider.stream(
        system="CV público", turns=[Turn("user", "¿Dónde trabaja?")], max_tokens=100,
        temperature=.3, usage=usage,
    )])


def test_gemini_request_usage_and_thoughts(monkeypatch):
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)

    def handler(request):
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        body = json.loads(request.content)
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
        assert body["systemInstruction"]["parts"][0]["text"] == "CV público"
        assert body["contents"][0]["role"] == "user"
        return httpx.Response(200, text=sse(
            {"candidates": [{"content": {"parts": [{"text": "privado", "thought": True}, {"text": "Carlos"}]}}]},
            candidate(" trabaja en BBVA.", "STOP"),
            {"usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20,
                               "thoughtsTokenCount": 7, "cachedContentTokenCount": 60}},
        ))

    usage = {}
    output = asyncio.run(collect(GeminiProvider("test-key", "gemini-2.5-flash", httpx.MockTransport(handler)), usage))
    assert output == "Carlos trabaja en BBVA."
    assert usage == {"input_tokens": 100, "output_tokens": 27, "reasoning_tokens": 7,
                     "cached_tokens": 60, "finish_reason": "stop"}


@pytest.mark.parametrize("event,code", [
    ({"promptFeedback": {"blockReason": "SAFETY"}}, "provider_content_filter"),
    (candidate("no mostrar", "SAFETY"), "provider_content_filter"),
    (candidate("", "STOP"), "provider_empty_response"),
    (candidate("parcial", None), "provider_incomplete_stream"),
    ({"error": {"message": "secret-key"}}, "provider_generation_error"),
    (candidate("", "OTHER"), "provider_generation_error"),
])
def test_gemini_does_not_report_failed_generations_as_completed(event, code):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=sse(event)))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(collect(GeminiProvider("test-key", "gemini-2.5-flash", transport)))
    assert exc.value.code == code
    assert "secret-key" not in str(exc.value)


@pytest.mark.parametrize("text", ["Respuesta parcial", ""])
def test_gemini_reports_token_limit_even_without_visible_text(text):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=sse(candidate(text, "MAX_TOKENS"))))
    usage = {}
    provider = GeminiProvider("test-key", "gemini-2.5-flash", transport)
    assert asyncio.run(collect(provider, usage)) == text
    assert usage["finish_reason"] == "max_output_tokens"


def test_http_error_never_contains_provider_body():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="secret-key and user's private prompt"))
    with pytest.raises(ProviderError, match="LLM HTTP 401") as exc:
        asyncio.run(collect(GeminiProvider("test-key", "gemini-2.5-flash", transport)))
    assert "secret-key" not in str(exc.value)
    assert "private" not in str(exc.value)


def test_timeout_is_safe_provider_error():
    def handler(request):
        raise httpx.ReadTimeout("private prompt secret-key", request=request)

    with pytest.raises(ProviderError) as exc:
        asyncio.run(collect(GeminiProvider("test-key", "gemini-2.5-flash", httpx.MockTransport(handler))))
    assert exc.value.code == "provider_timeout"
    assert "secret-key" not in str(exc.value)


def test_transient_status_retried_before_text(monkeypatch):
    calls = []

    async def no_wait(_):
        return None

    monkeypatch.setattr("app.providers.asyncio.sleep", no_wait)

    def handler(request):
        calls.append(request)
        return httpx.Response(503, text="private") if len(calls) == 1 else httpx.Response(200, text=sse(candidate()))

    output = asyncio.run(collect(GeminiProvider("test-key", "gemini-2.5-flash", httpx.MockTransport(handler))))
    assert len(calls) == 2 and output == "Carlos trabaja en BBVA."


def test_malformed_event_after_text_never_retries():
    calls, output = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=sse(candidate("parcial", None)) + "data: secret-key malformed\n\n")

    async def run():
        provider = GeminiProvider("test-key", "gemini-2.5-flash", httpx.MockTransport(handler))
        async for delta in provider.stream(system="CV", turns=[Turn("user", "hola")], max_tokens=100, temperature=0):
            output.append(delta)

    with pytest.raises(ProviderError) as exc:
        asyncio.run(run())
    assert output == ["parcial"] and len(calls) == 1
    assert exc.value.code == "provider_protocol_error" and "secret-key" not in str(exc.value)


def test_sse_multiline_event_and_comments():
    async def run():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, text=(
            ': keepalive\nevent: update\ndata: {"value":\ndata: "ok"}\n\ndata: [DONE]\n\n'
        )))
        async with httpx.AsyncClient(transport=transport) as client:
            return [event async for event in _sse_lines(client, "POST", "https://example.test")]

    assert asyncio.run(run()) == [{"value": "ok"}]


def test_current_model_does_not_receive_legacy_thinking_budget(monkeypatch):
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)

    def handler(request):
        assert 'gemini-3.5-flash-lite:streamGenerateContent' in request.url.path
        assert 'thinkingConfig' not in json.loads(request.content)['generationConfig']
        return httpx.Response(200, text=sse(candidate()))

    assert asyncio.run(collect(GeminiProvider('test-key', 'gemini-3.5-flash-lite', httpx.MockTransport(handler))))
