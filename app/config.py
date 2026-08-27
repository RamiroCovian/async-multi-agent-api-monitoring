"""Configuración de la aplicación vía variables de entorno."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["gemini", "openai", "anthropic"]
ObservabilityBackend = Literal["langsmith", "phoenix", "none"]


class Settings(BaseSettings):
    """Settings cargadas desde .env / entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"

    redis_url: str = "redis://localhost:6380/0"

    # Multi-LLM: gemini | openai | anthropic
    llm_provider: LlmProvider = "gemini"

    google_api_key: str = ""
    gemini_api_key: str = ""  # alias opcional de GOOGLE_API_KEY
    gemini_model: str = "gemini-2.0-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Observabilidad: langsmith | phoenix | none
    observability_backend: ObservabilityBackend = "langsmith"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "async-multi-agent-api-monitoring"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    phoenix_collector_endpoint: str = ""

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("observability_backend", mode="before")
    @classmethod
    def normalize_observability(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


@lru_cache
def get_settings() -> Settings:
    """Retorna settings cacheadas."""
    return Settings()
