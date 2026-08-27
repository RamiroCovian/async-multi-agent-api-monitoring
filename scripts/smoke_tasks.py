"""Smoke test local de /tasks (DONE + FAILED)."""

from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _wait_status(client: TestClient, job_id: str, timeout_s: float = 15.0) -> dict:
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        body = client.get(f"/tasks/{job_id}").json()
        if body.get("status") in {"DONE", "FAILED"}:
            return body
        time.sleep(0.2)
    raise AssertionError(f"timeout waiting job {job_id}: {body}")


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        print("health", health.status_code, health.json())

        created = client.post(
            "/tasks",
            json={"task": "Probar API async multiagente"},
        )
        print("create", created.status_code, created.json())
        assert created.status_code == 202
        done = _wait_status(client, created.json()["job_id"])
        print("done", done)
        assert done["status"] == "DONE"

        with patch("app.worker.run_graph", side_effect=RuntimeError("boom")):
            failed_create = client.post("/tasks", json={"task": "debe fallar"})
            assert failed_create.status_code == 202
            failed = _wait_status(client, failed_create.json()["job_id"])
        print("failed", failed)
        assert failed["status"] == "FAILED"
        assert "boom" in (failed.get("error") or "")

    print("ALL OK")


if __name__ == "__main__":
    main()
