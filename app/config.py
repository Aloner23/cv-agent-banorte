"""Configuración centralizada vía variables de entorno (12-factor)."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # Proveedor LLM: gemini | anthropic | openai | mock
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "gemini"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))

    demo_enabled: bool = field(default_factory=lambda: _env("DEMO_ENABLED", "false").lower() == "true")
    demo_daily_limit: int = field(default_factory=lambda: int(_env("DEMO_DAILY_LIMIT", "80")))
    demo_minute_limit: int = field(default_factory=lambda: int(_env("DEMO_MINUTE_LIMIT", "8")))

    # Seguridad del endpoint público
    agent_api_key: str = field(default_factory=lambda: _env("AGENT_API_KEY"))
    rate_limit_per_minute: int = field(default_factory=lambda: int(_env("RATE_LIMIT_PER_MINUTE", "30")))
    max_input_chars: int = field(default_factory=lambda: int(_env("MAX_INPUT_CHARS", "4000")))
    max_history_turns: int = field(default_factory=lambda: int(_env("MAX_HISTORY_TURNS", "12")))
    max_history_chars: int = field(default_factory=lambda: int(_env("MAX_HISTORY_CHARS", "16000")))
    max_output_tokens: int = field(default_factory=lambda: int(_env("MAX_OUTPUT_TOKENS", "900")))
    max_request_bytes: int = field(default_factory=lambda: int(_env("MAX_REQUEST_BYTES", "65536")))
    request_timeout_seconds: float = field(default_factory=lambda: float(_env("REQUEST_TIMEOUT_SECONDS", "90")))
    response_store_max_items: int = field(default_factory=lambda: int(_env("RESPONSE_STORE_MAX_ITEMS", "200")))
    response_store_ttl_seconds: int = field(default_factory=lambda: int(_env("RESPONSE_STORE_TTL_SECONDS", "3600")))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(x.strip() for x in _env("CORS_ORIGINS").split(",") if x.strip()))

    response_store_backend: str = field(default_factory=lambda: _env("RESPONSE_STORE_BACKEND", "memory"))
    google_cloud_project: str = field(default_factory=lambda: _env("GOOGLE_CLOUD_PROJECT"))
    firestore_database: str = field(default_factory=lambda: _env("FIRESTORE_DATABASE", "cv-agent"))
    firestore_collection: str = field(default_factory=lambda: _env("FIRESTORE_COLLECTION", "cv_responses"))

    # Estrategia de contexto: full (todo el CV en contexto) | retrieval (top-k secciones)
    knowledge_mode: str = field(default_factory=lambda: _env("KNOWLEDGE_MODE", "full"))
    retrieval_top_k: int = field(default_factory=lambda: int(_env("RETRIEVAL_TOP_K", "3")))
    knowledge_dir: Path = field(default_factory=lambda: Path(_env("KNOWLEDGE_DIR", str(ROOT / "knowledge"))))

    public_model_name: str = field(default_factory=lambda: _env("PUBLIC_MODEL_NAME", "carlos-cv-agent"))
    # Citas: hidden = el texto no muestra [id]; las fuentes viajan como annotations. inline = [id] visibles.
    citation_display: str = field(default_factory=lambda: _env("CITATION_DISPLAY", "hidden"))
    # URL pública (sin /v1) para la tarjeta de agente; si falta se deduce de la solicitud.
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL"))

    def __post_init__(self):
        for name in ("demo_daily_limit", "demo_minute_limit", "rate_limit_per_minute", "max_input_chars", "max_history_turns", "max_history_chars",
                     "max_output_tokens", "max_request_bytes", "request_timeout_seconds",
                     "response_store_max_items", "response_store_ttl_seconds", "retrieval_top_k"):
            if getattr(self, name) <= 0 or not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} debe ser mayor que cero")
        if self.response_store_backend not in ("memory", "firestore"):
            raise ValueError("RESPONSE_STORE_BACKEND debe ser memory o firestore")
        if self.response_store_backend == "firestore" and not self.google_cloud_project:
            raise ValueError("Firestore requiere GOOGLE_CLOUD_PROJECT")
        if self.citation_display not in ("hidden", "inline"):
            raise ValueError("CITATION_DISPLAY debe ser hidden o inline")
        if self.knowledge_mode not in ("full", "retrieval"):
            raise ValueError("KNOWLEDGE_MODE debe ser full o retrieval")

    def resolved_provider(self) -> str:
        """'auto' elige el primer proveedor con key disponible; si no hay, usa mock."""
        if self.llm_provider and self.llm_provider != "auto":
            return self.llm_provider
        if self.gemini_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "mock"


DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash-lite",
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4.1-mini",
    "mock": "mock-extractive",
}


def get_settings() -> Settings:
    return Settings()
