"""Servidor HTTP del agente de CV — endpoint compatible con Open Responses."""
from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .agent import CVAgent, InputError, Turn, SYSTEM_PROMPT
from .config import ROOT, get_settings
from .observability import Metrics, configure_logging, new_request_context
from .openresponses import (
    SSE,
    InvalidRequest,
    ResponseStore,
    error_body,
    citation_annotations,
    ignored_params,
    message_item,
    new_id,
    output_text_part,
    parse_input,
    response_obj,
    validate_body,
)
from .providers import DEFAULT_QUOTA_RETRY_SECONDS, ProviderError

configure_logging()
log = logging.getLogger("cv-agent")

settings = get_settings()
agent = CVAgent(settings)
store = ResponseStore(settings.response_store_max_items, settings.response_store_ttl_seconds)
metrics = Metrics()
titles = {d.doc_id: d.title for d in agent.kb.docs}
_hits: OrderedDict[str, deque] = OrderedDict()

APP_VERSION = "1.1.1"
app = FastAPI(title="Carlos Alonso · CV Agent", version=APP_VERSION, docs_url="/docs")
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "X-API-Key"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    rid = new_request_context(request.headers)
    t0 = time.perf_counter()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", None) or "unmatched"
    metrics.record_http(request.method, route, response.status_code)
    if route not in ("/health", "/ready"):  # los health checks del hosting solo generarían ruido
        log.info("http_request", extra={"fields": {"httpRequest": {
            "requestMethod": request.method, "requestUrl": route, "status": response.status_code,
            "latency": f"{time.perf_counter() - t0:.3f}s"}}})
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
    return response


# ------------------------------------------------------------------ seguridad
def _check_auth(request: Request) -> JSONResponse | None:
    if not settings.agent_api_key:
        return None
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
    if not hmac.compare_digest(token.encode(), settings.agent_api_key.encode()):
        return JSONResponse(error_body("API key inválida o ausente", "invalid_request", "invalid_api_key"), status_code=401)
    return None


def _check_rate(request: Request) -> JSONResponse | None:
    # Uvicorn puede resolver el proxy con una lista explícita de proxies confiables.
    # Nunca aceptamos x-forwarded-for directamente del cliente.
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    for key, timestamps in list(_hits.items()):
        if not timestamps or now - timestamps[-1] >= 60:
            _hits.pop(key, None)
    if ip not in _hits:
        if len(_hits) >= 4096:
            return JSONResponse(error_body("Demasiadas solicitudes, intenta en un minuto", "too_many_requests"),
                                status_code=429, headers={"Retry-After": "60"})
        _hits[ip] = deque()
    q = _hits[ip]
    while q and now - q[0] >= 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_minute:
        retry_after = max(1, int(60 - (now - q[0])) + 1)
        return JSONResponse(error_body("Demasiadas solicitudes, intenta en un minuto", "too_many_requests"),
                            status_code=429, headers={"Retry-After": str(retry_after)})
    q.append(now)
    return None


def _readiness_reasons() -> list[str]:
    reasons = []
    if agent.provider_name == "mock":
        reasons.append("demo_mode")
    elif not getattr(settings, f"{agent.provider_name}_api_key", ""):
        reasons.append("provider_credentials_missing")
    if not agent.kb.docs:
        reasons.append("knowledge_empty")
    return reasons


# ------------------------------------------------------------------ rutas informativas
@app.get("/")
def home():
    page = ROOT / "web" / "index.html"
    if page.exists():
        return FileResponse(page)
    return {"name": "Carlos Alonso CV Agent", "endpoint": "POST /v1/responses"}


@app.get("/health")
def health():
    reasons = _readiness_reasons()
    revision = os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_REVISION", "")
    return {
        "status": "ok",
        "version": APP_VERSION,
        "code_revision": revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None,
        "prompt_revision": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12],
        "ready": not reasons,
        "readiness_reasons": reasons,
        "readiness_check": "local_configuration_only",
        "provider": agent.provider_name,
        "model": agent.model,
        "public_model_name": settings.public_model_name,
        "knowledge_mode": settings.knowledge_mode,
        "knowledge_revision": getattr(agent.kb, "revision", None),
        "documents": len(agent.kb.docs),
        "chunks": len(agent.kb.chunks),
        "auth_required": bool(settings.agent_api_key),
    }


@app.get("/ready")
def ready():
    """La configuración está lista; no valida conectividad, cuota ni calidad del modelo."""
    state = health()
    return JSONResponse(state, status_code=200 if state["ready"] else 503)


@app.get("/v1/models")
def models(request: Request):
    if (err := _check_auth(request)):
        return err
    return {"object": "list", "data": [{"id": settings.public_model_name, "object": "model", "owned_by": "carlos-alonso"}]}


@app.get("/metrics")
def get_metrics(request: Request):
    """Métricas operativas de esta instancia (protegidas con la misma clave del agente)."""
    if (err := _check_auth(request)):
        return err
    return {"service": settings.public_model_name, "version": APP_VERSION,
            "provider": agent.provider_name, "model": agent.model,
            "knowledge_revision": getattr(agent.kb, "revision", None), **metrics.snapshot()}


def _public_base_url(request: Request) -> str:
    if settings.public_base_url:
        return settings.public_base_url.rstrip("/")
    # Detrás de Render/Cloud Run el esquema real llega en X-Forwarded-Proto (uvicorn --proxy-headers).
    return str(request.base_url).rstrip("/")


@app.get("/.well-known/agent-card.json")
def agent_card(request: Request):
    """Tarjeta de agente A2A: describe al agente y dónde está su endpoint Open Responses."""
    base = _public_base_url(request)
    responses_base = f"{base}/v1"
    return {
        "protocolVersion": "0.3.0",
        "name": "Carlos Alonso · Agente de CV",
        "description": ("Conversa sobre la trayectoria, experiencia, proyectos de IA y habilidades de "
                        "Carlos Ignacio Alonso Reyes, con respuestas basadas en su CV y referencias a las fuentes."),
        "url": responses_base,
        "preferredTransport": "HTTP+JSON",
        "additionalInterfaces": [{"url": responses_base, "transport": "HTTP+JSON"}],
        "version": APP_VERSION,
        "documentationUrl": "https://github.com/Aloner23/cv-agent-banorte",
        "provider": {"organization": "Carlos Ignacio Alonso Reyes", "url": "https://github.com/Aloner23"},
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": [{
                "uri": "https://www.openresponses.org/specification",
                "description": "Endpoint compatible con Open Responses: POST {url}/responses (con y sin SSE).",
                "required": False,
                "params": {"base_url": responses_base, "endpoint": f"{responses_base}/responses",
                           "model": settings.public_model_name,
                           "conversation_state": ["transcript_replay", "previous_response_id"]},
            }],
        },
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer",
                                       "description": "Authorization: Bearer <AGENT_API_KEY>"}},
        "security": [{"bearer": []}] if settings.agent_api_key else [],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{
            "id": "cv-qa",
            "name": "Preguntas sobre el CV",
            "description": "Responde sobre perfil, experiencia, proyectos, habilidades, formación y liderazgo, "
                           "sin inventar datos que no estén en el CV.",
            "tags": ["cv", "carrera", "ia", "banca"],
            "examples": [
                "¿Quién eres y cuál es tu perfil profesional?",
                "¿Qué proyectos de IA has construido y qué impacto tuvieron?",
                "¿Qué experiencia tienes liderando equipos?",
                "¿Cuáles son tus principales habilidades técnicas?",
            ],
        }],
    }


@app.get("/v1/responses/{resp_id}")
async def get_response(resp_id: str, request: Request):
    if (err := _check_auth(request)):
        return err
    found = store.get(resp_id)
    if not found:
        return JSONResponse(error_body(f"Response '{resp_id}' no encontrada", "not_found"), status_code=404)
    return found[1]


# ------------------------------------------------------------------ Open Responses
@app.post("/v1/responses")
async def create_response(request: Request):
    if (err := _check_auth(request)) or (err := _check_rate(request)):
        return err
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return JSONResponse(error_body("Content-Type debe ser application/json"), status_code=415)
    raw_body = bytearray()
    async for chunk in request.stream():
        if len(raw_body) + len(chunk) > settings.max_request_bytes:
            return JSONResponse(error_body("El cuerpo de la solicitud es demasiado grande", code="request_too_large"), status_code=413)
        raw_body.extend(chunk)
    try:
        body = validate_body(json.loads(raw_body))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        return JSONResponse(error_body("JSON inválido"), status_code=400)
    except InvalidRequest as e:
        return JSONResponse(error_body(str(e), code=e.code, param=e.param), status_code=400)

    if (skipped := ignored_params(body)):
        for name in skipped:
            metrics.ignored_params[name] += 1
        log.info("ignored_params", extra={"fields": {"params": skipped}})
        body = {k: v for k, v in body.items() if k not in skipped}

    if body.get("model") not in (None, settings.public_model_name):
        return JSONResponse(error_body("Modelo no encontrado; consulta /v1/models", code="model_not_found", param="model"), status_code=400)

    history = None
    prev = body.get("previous_response_id")
    if prev:
        found = store.get(prev)
        if not found:
            return JSONResponse(
                error_body(f"previous_response_id '{prev}' no encontrado", "not_found", "previous_response_not_found", "previous_response_id"),
                status_code=404,
            )
        history = found[0]

    try:
        req = agent.validate(parse_input(body, history))
    except InvalidRequest as e:
        return JSONResponse(error_body(str(e), code=e.code, param=e.param), status_code=400)
    except InputError as e:
        return JSONResponse(error_body(str(e), param="input"), status_code=400)

    reasons = _readiness_reasons()
    if "provider_credentials_missing" in reasons or "knowledge_empty" in reasons:
        return JSONResponse(error_body("El agente aún no está configurado para responder", "server_error", "agent_not_ready"), status_code=503)

    # La respuesta refleja la configuración efectiva, incluido el límite del servidor.
    body = dict(body)
    body["max_output_tokens"] = min(req.max_output_tokens or settings.max_output_tokens, settings.max_output_tokens)
    body["temperature"] = 0.3 if req.temperature is None else req.temperature

    model_name = body.get("model") or settings.public_model_name
    resp_id, msg_id, created = new_id("resp"), new_id("msg"), int(time.time())
    common = dict(resp_id=resp_id, created_at=created, model=model_name, body=body)
    t0 = time.perf_counter()

    def fail(code: str) -> None:
        metrics.record_error(code)
        log.warning("response_failed", extra={"fields": {
            "response_id": resp_id, "error_code": code, "ms": int((time.perf_counter() - t0) * 1000)}})

    def finish(text: str, usage: dict, ttft_ms: float | None = None) -> dict:
        reason = usage.get("finish_reason")
        incomplete = reason in ("max_output_tokens", "content_filter")
        status = "incomplete" if incomplete else "completed"
        annotations = citation_annotations(usage.get("citations"), titles)
        final = response_obj(**common, status=status, output=[message_item(msg_id, text, status, annotations)],
                             usage=usage, completed_at=int(time.time()),
                             incomplete_details={"reason": reason} if incomplete else None)
        if body.get("store", True) is not False:
            store.put(resp_id, req.turns + [Turn("assistant", text)], final)
        ms = (time.perf_counter() - t0) * 1000
        metrics.record_response(status, ms, usage, req.flags, ttft_ms)
        log.info("response", extra={"fields": {
            "response_id": resp_id, "status": status, "ms": int(ms),
            "ttft_ms": None if ttft_ms is None else int(ttft_ms), "stream": bool(body.get("stream")),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "flags": req.flags, "turns": len(req.turns), "finish_reason": usage.get("finish_reason"),
            "cited_sources": sorted({a["file_id"] for a in annotations}),
            "provider": agent.provider_name, "model": agent.model,
            "knowledge_revision": getattr(agent.kb, "revision", None)}})
        return final

    # ---------------- no streaming
    if not body.get("stream"):
        usage: dict = {}
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                text = "".join([d async for d in agent.stream(req, usage)])
            if not text.strip() and usage.get("finish_reason") not in ("max_output_tokens", "content_filter"):
                raise ProviderError("Empty provider response")
        except TimeoutError:
            fail("gateway_timeout")
            return JSONResponse(error_body("El modelo tardó demasiado, intenta de nuevo", "model_error", "gateway_timeout"), status_code=504)
        except ProviderError as e:
            fail(getattr(e, "code", None) or "model_error")
            if e.code == "provider_rate_limit":
                retry_after = e.retry_after or DEFAULT_QUOTA_RETRY_SECONDS
                return JSONResponse(error_body(
                    f"El proveedor limitó las solicitudes. Intenta de nuevo en {retry_after} segundos; si persiste, revisa la cuota.",
                    "model_error", "provider_rate_limit"), status_code=503,
                    headers={"Retry-After": str(retry_after)})
            return JSONResponse(error_body("El modelo no respondió, intenta de nuevo", "model_error", getattr(e, "code", "model_error")), status_code=502)
        return finish(text, usage)

    # ---------------- streaming SSE
    async def events():
        sse, usage, text, ttft = SSE(), {}, "", None
        yield sse("response.created", response=response_obj(**common, status="in_progress", output=[]))
        yield sse("response.in_progress", response=response_obj(**common, status="in_progress", output=[]))
        yield sse("response.output_item.added", output_index=0, item=message_item(msg_id, "", "in_progress"))
        yield sse("response.content_part.added", item_id=msg_id, output_index=0, content_index=0, part=output_text_part(""))
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                async for delta in agent.stream(req, usage):
                    if ttft is None and delta:
                        ttft = (time.perf_counter() - t0) * 1000
                    text += delta
                    yield sse("response.output_text.delta", item_id=msg_id, output_index=0, content_index=0, delta=delta, logprobs=[])
            if not text.strip() and usage.get("finish_reason") not in ("max_output_tokens", "content_filter"):
                raise ProviderError("Empty provider response")
        except Exception as e:  # noqa: BLE001 — cualquier fallo debe cerrar el stream con response.failed
            code = "gateway_timeout" if isinstance(e, TimeoutError) else getattr(e, "code", "server_error")
            fail(code)
            log.warning("stream_failure", extra={"fields": {"response_id": resp_id, "exception": type(e).__name__}})
            message = "El modelo tardó demasiado" if isinstance(e, TimeoutError) else "No fue posible completar la respuesta"
            if code == "provider_rate_limit":
                retry_after = getattr(e, "retry_after", None) or DEFAULT_QUOTA_RETRY_SECONDS
                message = f"El proveedor limitó las solicitudes. Intenta de nuevo en {retry_after} segundos; si persiste, revisa la cuota."
            failed = response_obj(**common, status="failed", output=[message_item(msg_id, text, "incomplete")] if text else [],
                                  usage=usage, error={"code": code, "message": message})
            yield sse("error", code=code, message=message, param=None)
            yield sse("response.failed", response=failed)
            yield "data: [DONE]\n\n"
            return
        final = finish(text, usage, ttft)
        part = final["output"][0]["content"][0]
        for i, annotation in enumerate(part["annotations"]):
            yield sse("response.output_text.annotation.added", item_id=msg_id, output_index=0, content_index=0,
                      annotation_index=i, annotation=annotation)
        yield sse("response.output_text.done", item_id=msg_id, output_index=0, content_index=0, text=text, logprobs=[])
        yield sse("response.content_part.done", item_id=msg_id, output_index=0, content_index=0, part=part)
        yield sse("response.output_item.done", output_index=0, item=final["output"][0])
        yield sse(f"response.{final['status']}", response=final)
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    # No registrar texto del proveedor ni payloads; podrían contener credenciales o CV.
    log.error("unhandled exception=%s", type(exc).__name__)
    return JSONResponse(error_body("Error interno", "server_error"), status_code=500)
