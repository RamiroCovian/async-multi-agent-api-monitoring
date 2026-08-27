"""Factory multi-provider de chat models (Gemini, OpenAI, Anthropic)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings

LlmProvider = Literal["gemini", "openai", "anthropic"]


def _resolve_api_key(settings: Settings) -> str:
    """Devuelve la API key del provider activo."""
    if settings.llm_provider == "gemini":
        return settings.google_api_key or settings.gemini_api_key
    if settings.llm_provider == "openai":
        return settings.openai_api_key
    if settings.llm_provider == "anthropic":
        return settings.anthropic_api_key
    raise ValueError(f"Provider no soportado: {settings.llm_provider}")


def _resolve_model(settings: Settings) -> str:
    """Devuelve el modelo del provider activo."""
    if settings.llm_provider == "gemini":
        return settings.gemini_model
    if settings.llm_provider == "openai":
        return settings.openai_model
    if settings.llm_provider == "anthropic":
        return settings.anthropic_model
    raise ValueError(f"Provider no soportado: {settings.llm_provider}")


def has_llm_credentials(settings: Settings | None = None) -> bool:
    """True si el provider activo tiene API key configurada."""
    cfg = settings or get_settings()
    return bool(_resolve_api_key(cfg).strip())


@lru_cache
def get_chat_model() -> BaseChatModel:
    """Instancia el chat model según LLM_PROVIDER.

    Providers: gemini (default), openai, anthropic.
    """
    settings = get_settings()
    provider: LlmProvider = settings.llm_provider  # type: ignore[assignment]
    api_key = _resolve_api_key(settings)
    model = _resolve_model(settings)

    if not api_key:
        raise RuntimeError(
            f"Falta API key para provider '{provider}'. "
            "Configurá la variable correspondiente en .env."
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.2,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0.2,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=0.2,
        )

    raise ValueError(f"Provider no soportado: {provider}")


def reset_chat_model_cache() -> None:
    """Limpia la cache del model (útil en tests o al cambiar env)."""
    get_chat_model.cache_clear()
