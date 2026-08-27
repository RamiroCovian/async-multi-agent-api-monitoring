"""Worker de jobs: PENDING / RUNNING / FAILED / DONE.

Implementación completa en feature/20260827_async-api.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Estados posibles de un job en Redis."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    DONE = "DONE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


async def enqueue_job(payload: dict) -> str:
    """Encola un job y retorna su job_id.

    Args:
        payload: Datos de la tarea a procesar.

    Returns:
        Identificador del job.
    """
    raise NotImplementedError("Worker pendiente (async-api)")


async def process_job(job_id: str) -> None:
    """Ejecuta el grafo para un job y actualiza estado en Redis.

    Ante excepción debe marcar el job como FAILED.
    """
    raise NotImplementedError("Worker pendiente (async-api)")
