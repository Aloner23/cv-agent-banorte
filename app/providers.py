"""Adaptadores de proveedores LLM sobre HTTP directo (httpx).

Decisión: en lugar de tres SDKs distintos usamos las APIs REST con streaming SSE.
Menos dependencias, mismo patrón para los tres proveedores, y el cambio de
proveedor es una variable de entorno (LLM_PROVIDER). Esto evita lock-in y permite
comparar modelos con la misma suite de evaluación.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, AsyncIterator, Protocol

import httpx

if TYPE_CHECKING:
    from .agent import Turn
    from .config import Settings
    from .knowledge import KnowledgeBase

log = logging.getLogger("cv-agent")
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
RETRY_STATUS = {429, 500, 502, 503, 504, 529}


class ProviderError(RuntimeError):
    """Error seguro para logs: nunca contiene cuerpos, prompts ni claves del proveedor."""

    def __init__(self, message: str, code: str = "model_error"):
        super().__init__(message)
        self.code = code


class Provider(Protocol):
    def stream(
        self, *, system: str, turns: list["Turn"], max_tokens: int, temperature: float, usage: dict | None = None
    ) -> AsyncIterator[str]: ...


async def _sse_lines(client: httpx.AsyncClient, method: str, url: str, **kw) -> AsyncIterator[dict]:
    """Parsea eventos SSE completos; reintenta HTTP transitorio antes de emitir texto.

    No reintenta errores de transporte tras abrir la solicitud: una repetición podría
    duplicar una generación facturada o texto que el usuario ya recibió.
    """
    try:
        for attempt in range(3):
            async with client.stream(method, url, **kw) as r:
                if r.status_code in RETRY_STATUS and attempt < 2:
                    await asyncio.sleep(0.8 * 2**attempt)
                    continue
                if r.status_code >= 400:
                    # El cuerpo puede repetir la entrada o una credencial: no leerlo ni registrarlo.
                    raise ProviderError(f"LLM HTTP {r.status_code}", "provider_http_error")
                data_lines: list[str] = []
                size = 0
                async for line in r.aiter_lines():
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip(" "))
                        size += len(line)
                        if size > 262_144:
                            raise ProviderError("Evento del modelo demasiado grande", "provider_protocol_error")
                    elif not line and data_lines:
                        raw = "\n".join(data_lines)
                        if raw.strip() == "[DONE]":
                            return
                        yield _parse_event(raw)
                        data_lines, size = [], 0
                if data_lines:
                    raw = "\n".join(data_lines)
                    if raw.strip() != "[DONE]":
                        yield _parse_event(raw)
                return
    except httpx.TimeoutException:
        raise ProviderError("El proveedor agotó el tiempo de espera", "provider_timeout") from None
    except httpx.HTTPError:
        raise ProviderError("No se pudo completar la conexión con el proveedor", "provider_connection_error") from None


def _parse_event(raw: str) -> dict:
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        raise ProviderError("El proveedor devolvió un evento inválido", "provider_protocol_error") from None
    if not isinstance(event, dict):
        raise ProviderError("El proveedor devolvió un evento inválido", "provider_protocol_error")
    if event.get("error"):
        raise ProviderError("El proveedor reportó un error", "provider_generation_error")
    return event


class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        self.key, self.model = api_key, model

    async def stream(self, *, system, turns, max_tokens, temperature, usage=None):
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            # Prompt caching: el CV es un prefijo estable → menor latencia y costo.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": t.role, "content": t.text} for t in turns],
        }
        headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            async for ev in _sse_lines(c, "POST", "https://api.anthropic.com/v1/messages", json=body, headers=headers):
                t = ev.get("type")
                if t == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                    yield ev["delta"]["text"]
                elif t == "message_start" and usage is not None:
                    u = ev["message"].get("usage", {})
                    usage["input_tokens"] = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                    usage["cached_tokens"] = u.get("cache_read_input_tokens", 0)
                elif t == "message_delta" and usage is not None:
                    usage["output_tokens"] = ev.get("usage", {}).get("output_tokens", 0)
                    reason = (ev.get("delta") or {}).get("stop_reason")
                    if reason:
                        usage["finish_reason"] = "max_output_tokens" if reason == "max_tokens" else "stop"
                elif t == "error":
                    raise ProviderError("El proveedor reportó un error", "provider_generation_error")


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.key, self.model = api_key, model

    async def stream(self, *, system, turns, max_tokens, temperature, usage=None):
        body = {
            "model": self.model,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system}] + [{"role": t.role, "content": t.text} for t in turns],
        }
        headers = {"Authorization": f"Bearer {self.key}"}
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            async for ev in _sse_lines(c, "POST", "https://api.openai.com/v1/chat/completions", json=body, headers=headers):
                for ch in ev.get("choices") or []:
                    d = (ch.get("delta") or {}).get("content")
                    if d:
                        yield d
                    if ch.get("finish_reason") and usage is not None:
                        usage["finish_reason"] = {"length": "max_output_tokens", "content_filter": "content_filter"}.get(ch["finish_reason"], "stop")
                if ev.get("usage") and usage is not None:
                    u = ev["usage"]
                    usage["input_tokens"] = u.get("prompt_tokens", 0)
                    usage["output_tokens"] = u.get("completion_tokens", 0)
                    usage["cached_tokens"] = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)


class GeminiProvider:
    def __init__(self, api_key: str, model: str, transport: httpx.AsyncBaseTransport | None = None):
        self.key, self.model = api_key, model
        self.transport = transport

    async def stream(self, *, system, turns, max_tokens, temperature, usage=None):
        gen = {"maxOutputTokens": max_tokens, "temperature": temperature}
        budget = os.getenv("GEMINI_THINKING_BUDGET")
        if budget is None and "2.5-flash" in self.model:
            budget = "0"  # respuestas de CV no requieren razonamiento extendido → menor latencia
        if budget is not None and budget != "":
            try:
                parsed_budget = int(budget)
                if parsed_budget < -1:
                    raise ValueError
            except ValueError:
                raise ProviderError("GEMINI_THINKING_BUDGET debe ser un entero >= -1", "provider_configuration_error") from None
            gen["thinkingConfig"] = {"thinkingBudget": parsed_budget}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user" if t.role == "user" else "model", "parts": [{"text": t.text}]} for t in turns],
            "generationConfig": gen,
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse"
        finish_reason, has_text = None, False
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as c:
            async for ev in _sse_lines(c, "POST", url, json=body, headers={"x-goog-api-key": self.key}):
                if ev.get("usageMetadata") and usage is not None:
                    u = ev["usageMetadata"]
                    # generateContent distingue respuesta visible y razonamiento facturable.
                    # https://ai.google.dev/api/generate-content#UsageMetadata
                    usage["input_tokens"] = u.get("promptTokenCount", 0) + u.get("toolUsePromptTokenCount", 0)
                    usage["output_tokens"] = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
                    usage["reasoning_tokens"] = u.get("thoughtsTokenCount", 0)
                    usage["cached_tokens"] = u.get("cachedContentTokenCount", 0)
                block = (ev.get("promptFeedback") or {}).get("blockReason")
                if block and block != "BLOCK_REASON_UNSPECIFIED":
                    raise ProviderError("El proveedor bloqueó la solicitud", "provider_content_filter")
                for cand in ev.get("candidates") or []:
                    if cand.get("index", 0) != 0:
                        continue
                    reason = cand.get("finishReason")
                    if reason and reason not in {"STOP", "MAX_TOKENS"}:
                        if reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                            raise ProviderError("El proveedor filtró la respuesta", "provider_content_filter")
                        raise ProviderError("El proveedor no terminó la respuesta normalmente", "provider_generation_error")
                    for p in (cand.get("content") or {}).get("parts") or []:
                        if p.get("text") and not p.get("thought"):
                            has_text = True
                            yield p["text"]
                    if reason:
                        finish_reason = "max_output_tokens" if reason == "MAX_TOKENS" else "stop"
                        if usage is not None:
                            usage["finish_reason"] = finish_reason
        if not finish_reason:
            raise ProviderError("El stream terminó sin confirmación del modelo", "provider_incomplete_stream")
        if not has_text and finish_reason != "max_output_tokens":
            raise ProviderError("El modelo no devolvió texto", "provider_empty_response")


class MockProvider:
    """Proveedor determinista sin red: responde con el fragmento más relevante.
    Sirve para tests, CI y para levantar el servicio sin API key."""

    def __init__(self, kb: "KnowledgeBase"):
        self.kb = kb

    async def stream(self, *, system, turns, max_tokens, temperature, usage=None):
        # Conserva referentes explícitos de preguntas previas, sin simular razonamiento.
        q = " ".join(turn.text for turn in turns if turn.role == "user")[-1500:]
        hits = self.kb.index.search(q, k=1)
        if hits:
            chunk = hits[0][0]
            lines = [l for l in chunk.text.splitlines() if l.strip() and not l.startswith("#")][:6]
            text = f"(modo demo sin LLM) Según la sección «{chunk.heading or chunk.title}» del CV de Carlos [{chunk.doc_id}]:\n" + "\n".join(lines)
        else:
            text = "(modo demo sin LLM) Eso no aparece en la información de Carlos que tengo. Puedes contactarlo por correo o LinkedIn."
        if usage is not None:
            # Estimación explícita: nunca debe confundirse con uso reportado por Gemini.
            usage.update(input_tokens=len(system) // 4, output_tokens=len(text) // 4, cached_tokens=0,
                         finish_reason="stop", estimated=True)
        for i in range(0, len(text), 40):
            yield text[i : i + 40]
            await asyncio.sleep(0)


def build_provider(name: str, s: "Settings", model: str, kb: "KnowledgeBase") -> Provider:
    if name == "anthropic":
        return AnthropicProvider(s.anthropic_api_key, model)
    if name == "openai":
        return OpenAIProvider(s.openai_api_key, model)
    if name == "gemini":
        return GeminiProvider(s.gemini_api_key, model)
    if name == "mock":
        return MockProvider(kb)
    raise ValueError(f"LLM_PROVIDER desconocido: {name}")
