"""Observabilidad: logs estructurados por solicitud y métricas operativas en memoria.

- Logs JSON compatibles con Cloud Logging (campo ``severity``, ``httpRequest`` y
  correlación con Cloud Trace vía ``X-Cloud-Trace-Context``). En local se usa texto.
- Cada solicitud recibe un ``X-Request-ID`` (se respeta el del cliente si es válido)
  que aparece en la respuesta y en todos los logs de esa solicitud.
- ``Metrics`` acumula conteos, latencias y tokens desde el arranque de la instancia.
  Es deliberadamente simple: con varias instancias cada una reporta lo suyo; la vista
  agregada se obtiene de Cloud Logging / Cloud Monitoring a partir de los logs.

Nunca se registran textos de usuario, respuestas del modelo ni credenciales.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import time
import uuid
from collections import Counter, deque
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
trace_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace", default=None)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SEVERITY = {"DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR", "CRITICAL": "CRITICAL"}


def use_json_logs() -> bool:
    fmt = os.getenv("LOG_FORMAT", "").strip().lower()
    if fmt in ("json", "text"):
        return fmt == "json"
    return bool(os.getenv("K_SERVICE"))  # Cloud Run define K_SERVICE


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": _SEVERITY.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
        }
        entry.update(getattr(record, "fields", None) or {})
        if (rid := request_id_var.get()):
            entry["request_id"] = rid
        if (trace := trace_var.get()):
            entry["logging.googleapis.com/trace"] = trace
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = dict(getattr(record, "fields", None) or {})
        if (rid := request_id_var.get()):
            extra["request_id"] = rid
        return f"{base} {json.dumps(extra, ensure_ascii=False, default=str)}" if extra else base


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if use_json_logs() else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def new_request_context(headers) -> str:
    """Fija request id y trace para la solicitud actual; devuelve el request id."""
    incoming = headers.get("x-request-id", "")
    rid = incoming if _SAFE_ID.match(incoming or "") else uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    trace_var.set(None)
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    cloud_trace = headers.get("x-cloud-trace-context", "")
    if project and cloud_trace:
        trace_id = cloud_trace.split("/", 1)[0]
        if re.fullmatch(r"[0-9a-f]{32}", trace_id):
            trace_var.set(f"projects/{project}/traces/{trace_id}")
    return rid


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[idx], 1)


class Metrics:
    """Métricas de la instancia desde que arrancó (ventana de latencia acotada)."""

    def __init__(self, window: int = 500):
        self.started = time.time()
        self.http = Counter()            # "POST /v1/responses 200" -> n
        self.responses = Counter()       # completed / incomplete / failed
        self.errors = Counter()          # código de error del agente o proveedor
        self.flags = Counter()           # guardrails activados
        self.ignored_params = Counter()
        self.tokens = Counter()          # input / output
        self.latency_ms: deque[float] = deque(maxlen=window)
        self.ttft_ms: deque[float] = deque(maxlen=window)

    def record_http(self, method: str, route: str, status: int) -> None:
        self.http[f"{method} {route} {status}"] += 1

    def record_response(self, status: str, ms: float, usage: dict, flags: list[str], ttft_ms: float | None = None):
        self.responses[status] += 1
        self.latency_ms.append(ms)
        if ttft_ms is not None:
            self.ttft_ms.append(ttft_ms)
        self.tokens["input"] += int(usage.get("input_tokens") or 0)
        self.tokens["output"] += int(usage.get("output_tokens") or 0)
        for f in flags:
            self.flags[f] += 1

    def record_error(self, code: str) -> None:
        self.responses["failed"] += 1
        self.errors[code] += 1

    def snapshot(self) -> dict:
        lat = list(self.latency_ms)
        ttft = list(self.ttft_ms)
        return {
            "scope": "instance",
            "instance_started_at": datetime.fromtimestamp(self.started, tz=timezone.utc).isoformat(),
            "uptime_seconds": int(time.time() - self.started),
            "responses": dict(self.responses),
            "errors": dict(self.errors),
            "guardrail_flags": dict(self.flags),
            "ignored_params": dict(self.ignored_params),
            "tokens": dict(self.tokens),
            "latency_ms": {"samples": len(lat), "p50": _percentile(lat, 50), "p95": _percentile(lat, 95)},
            "time_to_first_token_ms": {"samples": len(ttft), "p50": _percentile(ttft, 50), "p95": _percentile(ttft, 95)},
            "http": dict(self.http),
        }
