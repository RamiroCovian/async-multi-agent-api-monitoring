"""HITL: interrupt del grafo + endpoint de aprobación.

Implementación completa en feature/20260827_hitl.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["hitl"])


@router.post("/tasks/{job_id}/approve")
async def approve_task(job_id: str) -> dict[str, str]:
    """Aprueba un job pausado en nodo HITL y reanuda la ejecución.

    Args:
        job_id: Identificador del job en espera de aprobación.

    Returns:
        Confirmación de reanudación (placeholder).
    """
    return {"job_id": job_id, "detail": "not implemented"}
