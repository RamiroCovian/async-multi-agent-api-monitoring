"""Worker de jobs: PENDING / RUNNING / FAILED / DONE / AWAITING_APPROVAL.

Ejecuta el grafo fuera del event loop (`run_in_threadpool`) y marca FAILED
si hay excepción. Ante interrupt HITL marca AWAITING_APPROVAL.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from fastapi.concurrency import run_in_threadpool
from langgraph.checkpoint.redis import RedisSaver

from app.graph import resume_graph, run_graph

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


async def _persist_graph_result(
    job_id: str,
    *,
    job_store: JobStore,
    result: dict[str, Any],
) -> None:
    if result.get("__interrupted__"):
        await job_store.set_status(
            job_id,
            JobStatus.AWAITING_APPROVAL,
            current_agent="human_approval",
            plan=result.get("plan") or "",
            research=result.get("research") or "",
            analysis=result.get("analysis") or "",
            approval=result.get("approval") or "pending",
            error="",
        )
        return

    await job_store.set_status(
        job_id,
        JobStatus.DONE,
        result=result.get("result") or "",
        current_agent=result.get("current_agent") or "",
        plan=result.get("plan") or "",
        research=result.get("research") or "",
        analysis=result.get("analysis") or "",
        approval=result.get("approval") or "",
        error="",
    )


async def process_job(
    job_id: str,
    *,
    job_store: JobStore,
    checkpointer: RedisSaver,
) -> None:
    """Procesa un job: RUNNING → grafo → DONE | AWAITING_APPROVAL | FAILED."""
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
        await _persist_graph_result(job_id, job_store=job_store, result=result)
    except Exception as exc:
        logger.exception("Job %s falló", job_id)
        await job_store.set_status(
            job_id,
            JobStatus.FAILED,
            error=str(exc),
            result="",
        )


async def resume_job(
    job_id: str,
    *,
    approved: bool,
    job_store: JobStore,
    checkpointer: RedisSaver,
) -> None:
    """Reanuda un job pausado en HITL tras aprobación humana."""
    job = await job_store.get(job_id)
    if job is None:
        logger.error("Job no encontrado para resume: %s", job_id)
        return

    try:
        result = await run_in_threadpool(
            resume_graph,
            job_id,
            approved=approved,
            checkpointer=checkpointer,
        )
        await _persist_graph_result(job_id, job_store=job_store, result=result)
    except Exception as exc:
        logger.exception("Resume job %s falló", job_id)
        await job_store.set_status(
            job_id,
            JobStatus.FAILED,
            error=str(exc),
            result="",
        )
