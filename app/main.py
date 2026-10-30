"""Servidor HTTP del agente de CV — endpoint compatible con Open Responses."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from collections import OrderedDict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .agent import CVAgent, InputError, Turn
from .config import ROOT, get_settings
from .openresponses import (
    SSE,
    InvalidRequest,
    ResponseStore,
    error_body,
    message_item,
    new_id,
    output_text_part,
    parse_input,
    response_obj,
    validate_body,
)
from .providers import ProviderError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cv-agent")

settings = get_settings()
agent = CVAgent(settings)
store = ResponseStore(settings.response_store_max_items, settings.response_store_ttl_seconds)
_hits: OrderedDict[str, deque] = OrderedDict()

app = FastAPI(title="Carlos Alonso · CV Agent", version="1.0.0", docs_url="/docs")
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "X-API-Key"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
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
    return {
        "status": "ok",
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

    def finish(text: str, usage: dict) -> dict:
        reason = usage.get("finish_reason")
        incomplete = reason in ("max_output_tokens", "content_filter")
        status = "incomplete" if incomplete else "completed"
        final = response_obj(**common, status=status, output=[message_item(msg_id, text, status)],
                             usage=usage, completed_at=int(time.time()),
                             incomplete_details={"reason": reason} if incomplete else None)
        if body.get("store", True) is not False:
            store.put(resp_id, req.turns + [Turn("assistant", text)], final)
        log.info(json.dumps({"event": "response", "id": resp_id, "ms": int((time.perf_counter() - t0) * 1000),
                             "in_tok": usage.get("input_tokens"), "out_tok": usage.get("output_tokens"),
                             "flags": req.flags, "turns": len(req.turns), "status": status,
                             "knowledge_revision": getattr(agent.kb, "revision", None)}))
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
            log.warning("response timeout id=%s", resp_id)
            return JSONResponse(error_body("El modelo tardó demasiado, intenta de nuevo", "model_error", "gateway_timeout"), status_code=504)
        except ProviderError as e:
            log.warning("provider failure id=%s code=%s", resp_id, getattr(e, "code", "model_error"))
            return JSONResponse(error_body("El modelo no respondió, intenta de nuevo", "model_error", getattr(e, "code", "model_error")), status_code=502)
        return finish(text, usage)

    # ---------------- streaming SSE
    async def events():
        sse, usage, text = SSE(), {}, ""
        yield sse("response.created", response=response_obj(**common, status="in_progress", output=[]))
        yield sse("response.in_progress", response=response_obj(**common, status="in_progress", output=[]))
        yield sse("response.output_item.added", output_index=0, item=message_item(msg_id, "", "in_progress"))
        yield sse("response.content_part.added", item_id=msg_id, output_index=0, content_index=0, part=output_text_part(""))
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                async for delta in agent.stream(req, usage):
                    text += delta
                    yield sse("response.output_text.delta", item_id=msg_id, output_index=0, content_index=0, delta=delta, logprobs=[])
            if not text.strip() and usage.get("finish_reason") not in ("max_output_tokens", "content_filter"):
                raise ProviderError("Empty provider response")
        except Exception as e:  # noqa: BLE001 — cualquier fallo debe cerrar el stream con response.failed
            code = "gateway_timeout" if isinstance(e, TimeoutError) else getattr(e, "code", "server_error")
            log.warning("stream failure id=%s code=%s exception=%s", resp_id, code, type(e).__name__)
            message = "El modelo tardó demasiado" if isinstance(e, TimeoutError) else "No fue posible completar la respuesta"
            failed = response_obj(**common, status="failed", output=[message_item(msg_id, text, "incomplete")] if text else [],
                                  usage=usage, error={"code": code, "message": message})
            yield sse("error", code=code, message=message, param=None)
            yield sse("response.failed", response=failed)
            yield "data: [DONE]\n\n"
            return
        final = finish(text, usage)
        yield sse("response.output_text.done", item_id=msg_id, output_index=0, content_index=0, text=text, logprobs=[])
        yield sse("response.content_part.done", item_id=msg_id, output_index=0, content_index=0, part=output_text_part(text))
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
