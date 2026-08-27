"""Punto de entrada FastAPI: health y stubs de /tasks."""

from __future__ import annotations

from fastapi import FastAPI

from app.hitl import router as hitl_router

app = FastAPI(
    title="Async Multi-Agent API Monitoring",
    description=(
        "API REST asíncrona para sistema multiagente (LangGraph) "
        "con jobs en Redis, observabilidad y HITL."
    ),
    version="0.1.0",
)

app.include_router(hitl_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Verifica que la API responde."""
    return {"status": "ok"}


@app.post("/tasks", status_code=202)
async def create_task() -> dict[str, str]:
    """Recibe una tarea, la encola y devuelve job_id (sin bloquear).

    Implementación completa en feature/20260827_async-api.
    """
    return {"detail": "not implemented", "job_id": ""}


@app.get("/tasks/{job_id}")
async def get_task(job_id: str) -> dict[str, str]:
    """Consulta el estado de un job en Redis.

    Implementación completa en feature/20260827_async-api.
    """
    return {"job_id": job_id, "status": "PENDING", "detail": "not implemented"}
