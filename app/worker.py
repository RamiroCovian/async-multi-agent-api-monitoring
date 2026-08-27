"""Worker de jobs: PENDING / RUNNING / FAILED / DONE.

Ejecuta el grafo fuera del event loop (`run_in_threadpool`) y marca FAILED
si hay excepción.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool
from langgraph.checkpoint.redis import RedisSaver

from app.graph import run_graph

if TYPE_CHECKING:
    from app.jobs import JobStore

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    """Estados posibles de un job en Redis."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    DONE = "DONE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


async def process_job(
    job_id: str,
    *,
    job_store: JobStore,
    checkpointer: RedisSaver,
) -> None:
    """Procesa un job: RUNNING → grafo → DONE | FAILED.

    Args:
        job_id: Identificador del job.
        job_store: Persistencia async de estado operativo.
        checkpointer: RedisSaver compartido para LangGraph.
    """
    job = await job_store.get(job_id)
    if job is None:
        logger.error("Job no encontrado: %s", job_id)
        return

    task = job.get("task") or ""
    await job_store.set_status(job_id, JobStatus.RUNNING)

    try:
        result = await run_in_threadpool(
            run_graph,
            task,
            thread_id=job_id,
            checkpointer=checkpointer,
        )
        await job_store.set_status(
            job_id,
            JobStatus.DONE,
            result=result.get("result") or "",
            current_agent=result.get("current_agent") or "",
            plan=result.get("plan") or "",
            research=result.get("research") or "",
            analysis=result.get("analysis") or "",
            error="",
        )
    except Exception as exc:
        logger.exception("Job %s falló", job_id)
        await job_store.set_status(
            job_id,
            JobStatus.FAILED,
            error=str(exc),
            result="",
        )
