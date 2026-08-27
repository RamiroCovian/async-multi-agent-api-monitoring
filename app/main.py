"""Punto de entrada FastAPI: tasks async con jobs en Redis."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from redis.asyncio import Redis

from app.config import get_settings
from app.graph import create_checkpointer
from app.hitl import router as hitl_router
from app.jobs import JobStore
from app.schemas import TaskCreate, TaskCreated, TaskStatusResponse
from app.worker import JobStatus, process_job


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicializa Redis (jobs) y RedisSaver (checkpoints LangGraph)."""
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    checkpointer = create_checkpointer(settings.redis_url)

    app.state.settings = settings
    app.state.redis = redis
    app.state.job_store = JobStore(redis)
    app.state.checkpointer = checkpointer

    yield

    await redis.aclose()


app = FastAPI(
    title="Async Multi-Agent API Monitoring",
    description=(
        "API REST asíncrona para sistema multiagente (LangGraph) "
        "con jobs en Redis, observabilidad y HITL."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(hitl_router)


def _job_store(request: Request) -> JobStore:
    return request.app.state.job_store


@app.get("/health")
async def health() -> dict[str, str]:
    """Verifica que la API responde."""
    return {"status": "ok"}


@app.post("/tasks", status_code=202, response_model=TaskCreated)
async def create_task(
    payload: TaskCreate,
    background_tasks: BackgroundTasks,
    request: Request,
) -> TaskCreated:
    """Encola una tarea y devuelve `job_id` sin bloquear el event loop."""
    store = _job_store(request)
    job_id = await store.create(payload.task)

    background_tasks.add_task(
        process_job,
        job_id,
        job_store=store,
        checkpointer=request.app.state.checkpointer,
    )
    return TaskCreated(job_id=job_id, status=JobStatus.PENDING)


@app.get("/tasks/{job_id}", response_model=TaskStatusResponse)
async def get_task(job_id: str, request: Request) -> TaskStatusResponse:
    """Consulta el estado de un job en Redis."""
    job = await _job_store(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    status = JobStatus(job.get("status") or JobStatus.PENDING)
    return TaskStatusResponse(
        job_id=job_id,
        status=status,
        task=job.get("task") or None,
        result=job.get("result") or None,
        error=job.get("error") or None,
        current_agent=job.get("current_agent") or None,
        created_at=job.get("created_at") or None,
        updated_at=job.get("updated_at") or None,
    )
