"""Capa de compatibilidad con la especificación Open Responses (POST /v1/responses).

Traduce el payload Open Responses ⇄ el modelo interno del agente (AgentRequest/Turn)
y emite los eventos SSE semánticos en el orden que exige la especificación:
response.created → response.in_progress → response.output_item.added →
response.content_part.added → response.output_text.delta* → response.output_text.done →
response.content_part.done → response.output_item.done → response.completed/incomplete.
Los fallos emiten error seguido de response.failed.
"""
from __future__ import annotations

import json
import math
import secrets
import time
from collections import OrderedDict
from typing import Any

from .agent import AgentRequest, Turn


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


class InvalidRequest(ValueError):
    def __init__(self, message: str, param: str | None = None, code: str = "invalid_request"):
        super().__init__(message)
        self.param, self.code = param, code


# ---------------------------------------------------------------- entrada
def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") not in ("input_text", "output_text"):
                raise InvalidRequest("Sólo se admiten partes input_text y output_text", "input", "unsupported_content")
            if not isinstance(part.get("text"), str):
                raise InvalidRequest("El texto de cada parte debe ser string", "input")
            out.append(part["text"])
        return "\n".join(t for t in out if t)
    raise InvalidRequest("Formato de content no soportado", "input")


def validate_body(body: Any) -> dict:
    """Valida el subconjunto textual antes de usar IDs o construir mensajes.

    Rechazar capacidades no implementadas evita aparentar que se ejecutaron
    herramientas, imágenes o salida estructurada que el agente no soporta.
    """
    if not isinstance(body, dict):
        raise InvalidRequest("El cuerpo debe ser un objeto JSON")
    supported = {"input", "instructions", "model", "previous_response_id", "stream", "store", "metadata", "user",
                 "max_output_tokens", "temperature", "tools", "tool_choice", "parallel_tool_calls", "background",
                 "truncation", "text", "top_p"}
    for name in body.keys() - supported:
        if body[name] is not None:
            raise InvalidRequest(f"El parámetro '{name}' no está soportado", name, "unsupported_parameter")
    for name in ("model", "previous_response_id", "instructions", "user"):
        value = body.get(name)
        if value is not None and (not isinstance(value, str) or (name != "instructions" and not value.strip())):
            raise InvalidRequest(f"'{name}' debe ser un string no vacío", name)
    if body.get("previous_response_id") and len(body["previous_response_id"]) > 128:
        raise InvalidRequest("previous_response_id demasiado largo", "previous_response_id")
    for name in ("stream", "store", "background", "parallel_tool_calls"):
        if name in body and not isinstance(body[name], bool):
            raise InvalidRequest(f"'{name}' debe ser booleano", name)
    if "max_output_tokens" in body and body["max_output_tokens"] is not None:
        value = body["max_output_tokens"]
        if type(value) is not int or value < 1:
            raise InvalidRequest("max_output_tokens debe ser un entero positivo", "max_output_tokens")
    if "temperature" in body and body["temperature"] is not None:
        value = body["temperature"]
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise InvalidRequest("temperature debe estar entre 0 y 1", "temperature")
    if body.get("top_p") is not None and type(body["top_p"]) not in (int, float):
        raise InvalidRequest("top_p debe ser numérico", "top_p")
    metadata = body.get("metadata")
    if metadata is not None and (not isinstance(metadata, dict) or len(metadata) > 16 or
                                any(not isinstance(v, str) or len(k) > 64 or len(v) > 512 for k, v in metadata.items())):
        raise InvalidRequest("metadata admite hasta 16 pares string (clave 64, valor 512 caracteres)", "metadata")
    for name, allowed in (("tools", ([],)), ("tool_choice", ("auto", "none")),
                          ("background", (False,)), ("parallel_tool_calls", (False,)),
                          ("truncation", ("disabled",)), ("top_p", (1, 1.0)),
                          ("text", ({"format": {"type": "text"}},))):
        if name in body and body[name] is not None and body[name] not in allowed:
            raise InvalidRequest(f"Valor de '{name}' no soportado por este agente textual", name, "unsupported_parameter")
    return body


def parse_input(body: dict, history: list[Turn] | None = None) -> AgentRequest:
    validate_body(body)
    raw = body.get("input")
    if raw is None:
        raise InvalidRequest("Falta el campo 'input'", "input")

    turns: list[Turn] = list(history or [])
    extra_instructions: list[str] = []
    if isinstance(raw, str):
        turns.append(Turn("user", raw))
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                raise InvalidRequest("Cada elemento de 'input' debe ser un objeto", "input")
            itype = item.get("type", "message")
            if itype != "message":
                raise InvalidRequest("Sólo se admiten items de tipo message", "input", "unsupported_item")
            role = item.get("role", "user")
            if role not in ("system", "developer", "user", "assistant"):
                raise InvalidRequest("Rol de mensaje no soportado", "input")
            text = _content_to_text(item.get("content"))
            if role in ("system", "developer"):
                extra_instructions.append(text)
            elif role in ("user", "assistant") and text.strip():
                # fusiona turnos consecutivos del mismo rol (requisito de algunos proveedores)
                if turns and turns[-1].role == role:
                    turns[-1] = Turn(role, turns[-1].text + "\n" + text)
                else:
                    turns.append(Turn(role, text))
    else:
        raise InvalidRequest("'input' debe ser string o lista de items", "input")

    # algunos proveedores exigen que el primer turno sea del usuario
    while turns and turns[0].role != "user":
        turns.pop(0)

    instr = "\n".join(x for x in [body.get("instructions") or "", *extra_instructions] if x).strip() or None
    max_out = body.get("max_output_tokens")
    temp = body.get("temperature")
    return AgentRequest(
        turns=turns,
        client_instructions=instr,
        max_output_tokens=max_out,
        temperature=temp,
    )


# ---------------------------------------------------------------- salida
def message_item(item_id: str, text: str, status: str) -> dict:
    return {
        "type": "message",
        "id": item_id,
        "status": status,
        "role": "assistant",
        "content": [] if status == "in_progress" and not text else [output_text_part(text)],
    }


def output_text_part(text: str) -> dict:
    return {"type": "output_text", "text": text, "annotations": [], "logprobs": []}


def usage_obj(u: dict | None) -> dict | None:
    if not u:
        return None
    i, o = int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))
    return {
        "input_tokens": i,
        "output_tokens": o,
        "total_tokens": i + o,
        "input_tokens_details": {"cached_tokens": int(u.get("cached_tokens", 0))},
        "output_tokens_details": {"reasoning_tokens": int(u.get("reasoning_tokens", 0))},
    }


def response_obj(
    *,
    resp_id: str,
    created_at: int,
    status: str,
    model: str,
    body: dict,
    output: list[dict],
    usage: dict | None = None,
    error: dict | None = None,
    completed_at: int | None = None,
    incomplete_details: dict | None = None,
) -> dict:
    text = "".join(p.get("text", "") for it in output if it.get("type") == "message" for p in it.get("content", []))
    return {
        "id": resp_id,
        "object": "response",
        "created_at": created_at,
        "completed_at": completed_at,
        "status": status,
        "error": error,
        "incomplete_details": incomplete_details,
        "model": model,
        "previous_response_id": body.get("previous_response_id"),
        "instructions": body.get("instructions"),
        "output": output,
        "output_text": text,  # conveniencia (SDKs de OpenAI la exponen)
        "tools": [],
        "tool_choice": body.get("tool_choice") or "auto",
        "parallel_tool_calls": False,
        "truncation": body.get("truncation") or "disabled",
        "text": {"format": {"type": "text"}},
        "temperature": body.get("temperature", 0.3) if isinstance(body.get("temperature"), (int, float)) else 0.3,
        "top_p": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "top_logprobs": 0,
        "reasoning": None,
        "usage": usage_obj(usage),
        "max_output_tokens": body.get("max_output_tokens"),
        "max_tool_calls": None,
        "store": bool(body.get("store", True)),
        "background": False,
        "service_tier": "default",
        "metadata": body.get("metadata") or {},
        "safety_identifier": None,
        "prompt_cache_key": None,
        "user": body.get("user"),
    }


def error_body(message: str, type_: str = "invalid_request", code: str | None = None, param: str | None = None) -> dict:
    return {"error": {"message": message, "type": type_, "code": code or type_, "param": param}}


class SSE:
    """Serializa eventos con `event:` igual al `type` y `sequence_number` creciente."""

    def __init__(self):
        self.seq = 0

    def __call__(self, type_: str, **payload) -> str:
        ev = {"type": type_, "sequence_number": self.seq, **payload}
        self.seq += 1
        return f"event: {type_}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------- memoria de conversaciones
class ResponseStore:
    """Almacén en memoria (LRU + TTL) para `previous_response_id` y GET /v1/responses/{id}.
    En producción multi-instancia se reemplazaría por Redis; para este reto una
    sola instancia es suficiente y evita dependencias."""

    def __init__(self, max_items: int = 200, ttl_s: int = 3600):
        self.data: OrderedDict[str, tuple[float, list[Turn], dict]] = OrderedDict()
        self.max_items, self.ttl = max_items, ttl_s

    def put(self, resp_id: str, turns: list[Turn], response: dict) -> None:
        now = time.monotonic()
        for key, (ts, _, _) in list(self.data.items()):
            if now - ts >= self.ttl:
                self.data.pop(key, None)
        self.data[resp_id] = (now, list(turns), response)
        self.data.move_to_end(resp_id)
        while len(self.data) > self.max_items:
            self.data.popitem(last=False)

    def get(self, resp_id: str) -> tuple[list[Turn], dict] | None:
        v = self.data.get(resp_id)
        if not v:
            return None
        ts, turns, resp = v
        if time.monotonic() - ts >= self.ttl:
            self.data.pop(resp_id, None)
            return None
        self.data.move_to_end(resp_id)
        return list(turns), resp
