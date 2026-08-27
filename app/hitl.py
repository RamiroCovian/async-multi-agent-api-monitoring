"""HITL: interrupt del grafo + endpoint de aprobación humana."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.schemas import TaskApprovalRequest, TaskApprovalResponse
from app.worker import JobStatus, resume_job

router = APIRouter(tags=["hitl"])


@router.post("/tasks/{job_id}/approve", response_model=TaskApprovalResponse)
async def approve_task(
    job_id: str,
    payload: TaskApprovalRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> TaskApprovalResponse:
    """Aprueba o rechaza un job pausado en el nodo HITL y reanuda el grafo."""
    store = request.app.state.job_store
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    status = JobStatus(job.get("status") or JobStatus.PENDING)
    if status != JobStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"job is not awaiting approval (status={status.value})",
        )

    await store.set_status(job_id, JobStatus.RUNNING)
    background_tasks.add_task(
        resume_job,
        job_id,
        approved=payload.approved,
        job_store=store,
        checkpointer=request.app.state.checkpointer,
    )

    return TaskApprovalResponse(
        job_id=job_id,
        status=JobStatus.RUNNING,
        approved=payload.approved,
        detail="resume queued",
    )
