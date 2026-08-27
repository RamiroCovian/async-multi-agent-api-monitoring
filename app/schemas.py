"""Schemas Pydantic de la API de tasks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.worker import JobStatus


class TaskCreate(BaseModel):
    """Payload para encolar una tarea multiagente."""

    task: str = Field(..., min_length=1, description="Descripción de la tarea a ejecutar")


class TaskCreated(BaseModel):
    """Respuesta inmediata al encolar (202)."""

    job_id: str
    status: JobStatus = JobStatus.PENDING


class TaskStatusResponse(BaseModel):
    """Estado y resultado de un job."""

    job_id: str
    status: JobStatus
    task: str | None = None
    result: str | None = None
    error: str | None = None
    current_agent: str | None = None
    approval: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    extras: dict[str, Any] | None = None


class TaskApprovalRequest(BaseModel):
    """Payload para aprobar o rechazar un job en HITL."""

    approved: bool = Field(..., description="True para aprobar y continuar; False para rechazar")


class TaskApprovalResponse(BaseModel):
    """Confirmación de reanudación HITL."""

    job_id: str
    status: JobStatus
    approved: bool
    detail: str
