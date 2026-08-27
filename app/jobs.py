"""Persistencia de jobs en Redis (estado operativo, aparte de checkpoints LangGraph)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

from app.worker import JobStatus

JOB_KEY_PREFIX = "job:"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


class JobStore:
    """CRUD async de jobs en Redis (hashes JSON-friendly)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, task: str) -> str:
        """Crea un job PENDING y retorna su job_id."""
        job_id = str(uuid4())
        now = _utcnow()
        payload = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "task": task,
            "result": "",
            "error": "",
            "current_agent": "",
            "created_at": now,
            "updated_at": now,
        }
        await self._redis.hset(job_key(job_id), mapping=payload)
        return job_id

    async def get(self, job_id: str) -> dict[str, Any] | None:
        """Obtiene un job o None si no existe."""
        data = await self._redis.hgetall(job_key(job_id))
        if not data:
            return None
        return _decode_hash(data)

    async def update(self, job_id: str, **fields: Any) -> None:
        """Actualiza campos del job y `updated_at`."""
        if not fields:
            return
        payload = {k: _serialize(v) for k, v in fields.items()}
        payload["updated_at"] = _utcnow()
        await self._redis.hset(job_key(job_id), mapping=payload)

    async def set_status(self, job_id: str, status: JobStatus, **fields: Any) -> None:
        """Cambia status y campos opcionales."""
        await self.update(job_id, status=status.value, **fields)


def _serialize(value: Any) -> str:
    if isinstance(value, JobStatus):
        return value.value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _decode_hash(data: dict[Any, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in data.items():
        k = key.decode() if isinstance(key, bytes) else str(key)
        v = value.decode() if isinstance(value, bytes) else value
        decoded[k] = v
    return decoded
