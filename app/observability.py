"""Observabilidad: LangSmith (default) u opcional Arize Phoenix / OpenInference."""

from __future__ import annotations

import logging
import os
from functools import wraps
from typing import Any, Callable, Literal, TypeVar

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

ObservabilityBackend = Literal["langsmith", "phoenix", "none"]
F = TypeVar("F", bound=Callable[..., Any])

_configured = False


def configure_observability(settings: Settings | None = None) -> ObservabilityBackend:
    """Configura trazas según backend (idempotente).

    - langsmith: LANGCHAIN_TRACING_V2 + API key (auto-traza LangChain/LangGraph)
    - phoenix: OpenInference + colector Phoenix (requiere paquetes opcionales)
    - none: sin trazas
    """
    global _configured
    if _configured:
        return _active_backend()

    cfg = settings or get_settings()
    backend = cfg.observability_backend

    if backend == "langsmith":
        _configure_langsmith(cfg)
    elif backend == "phoenix":
        _configure_phoenix(cfg)
    else:
        logger.info("Observabilidad deshabilitada (backend=none)")

    _configured = True
    logger.info("Observabilidad activa: backend=%s", backend)
    return backend


def _active_backend() -> ObservabilityBackend:
    return get_settings().observability_backend


def _configure_langsmith(cfg: Settings) -> None:
    if not cfg.langchain_tracing_v2:
        logger.info("LangSmith deshabilitado (LANGCHAIN_TRACING_V2=false)")
        return
    if not cfg.langchain_api_key:
        logger.warning("LangSmith habilitado pero falta LANGCHAIN_API_KEY")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = cfg.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = cfg.langchain_project
    if cfg.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = cfg.langchain_endpoint

    logger.info("LangSmith configurado (project=%s)", cfg.langchain_project)


def _configure_phoenix(cfg: Settings) -> None:
    if not cfg.phoenix_collector_endpoint:
        logger.warning("Phoenix sin PHOENIX_COLLECTOR_ENDPOINT; omitiendo instrumentación")
        return

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register
    except ImportError as exc:
        raise RuntimeError(
            "Backend phoenix requiere: pip install arize-phoenix openinference-instrumentation-langchain"
        ) from exc

    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", cfg.phoenix_collector_endpoint)
    tracer_provider = register(
        project_name=cfg.langchain_project,
        endpoint=cfg.phoenix_collector_endpoint,
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("Phoenix instrumentado (%s)", cfg.phoenix_collector_endpoint)


def trace_llm_call(agent_name: str) -> Callable[[F], F]:
    """Decorador de trazas para llamadas LLM por agente."""

    def decorator(func: F) -> F:
        if get_settings().observability_backend == "none":
            return func

        try:
            from langsmith import traceable

            traced = traceable(
                name=f"{agent_name}_llm",
                run_type="llm",
                metadata={"agent": agent_name},
            )(func)
            return traced  # type: ignore[return-value]
        except Exception:
            return _fallback_trace(func, agent_name, "llm")

    return decorator


def trace_agent_node(agent_name: str) -> Callable[[F], F]:
    """Decorador de trazas para nodos del grafo multiagente."""

    def decorator(func: F) -> F:
        if get_settings().observability_backend == "none":
            return func

        try:
            from langsmith import traceable

            traced = traceable(
                name=f"{agent_name}_node",
                run_type="chain",
                metadata={"agent": agent_name},
            )(func)
            return traced  # type: ignore[return-value]
        except Exception:
            return _fallback_trace(func, agent_name, "chain")

    return decorator


def _fallback_trace(func: F, name: str, run_type: str) -> F:
    """Wrapper mínimo si LangSmith no está disponible."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("trace %s (%s) start", name, run_type)
        try:
            return func(*args, **kwargs)
        finally:
            logger.debug("trace %s (%s) end", name, run_type)

    return wrapper  # type: ignore[return-value]


def graph_run_config(thread_id: str, task: str) -> dict[str, Any]:
    """Config LangGraph con metadata/tags para el dashboard."""
    cfg = get_settings()
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"job-{thread_id[:8]}",
        "metadata": {
            "job_id": thread_id,
            "task_preview": task[:120],
            "llm_provider": cfg.llm_provider,
            "observability_backend": cfg.observability_backend,
        },
        "tags": ["multi-agent", "api", cfg.llm_provider],
    }
    return config


def is_tracing_enabled() -> bool:
    """True si hay backend de observabilidad activo y configurado."""
    cfg = get_settings()
    if cfg.observability_backend == "none":
        return False
    if cfg.observability_backend == "langsmith":
        return cfg.langchain_tracing_v2 and bool(cfg.langchain_api_key)
    if cfg.observability_backend == "phoenix":
        return bool(cfg.phoenix_collector_endpoint)
    return False
