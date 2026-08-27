"""Smoke test HITL: AWAITING_APPROVAL → approve → DONE."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app


def _wait_status(client: TestClient, job_id: str, wanted: set[str], timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        body = client.get(f"/tasks/{job_id}").json()
        if body.get("status") in wanted:
            return body
        time.sleep(0.2)
    raise AssertionError(f"timeout waiting {wanted} for {job_id}: {body}")


def main() -> None:
    with TestClient(app) as client:
        created = client.post("/tasks", json={"task": "Probar HITL en pipeline multiagente"})
        assert created.status_code == 202
        job_id = created.json()["job_id"]

        awaiting = _wait_status(client, job_id, {"AWAITING_APPROVAL"})
        print("awaiting", awaiting)
        assert awaiting["current_agent"] == "human_approval"

        approve = client.post(f"/tasks/{job_id}/approve", json={"approved": True})
        print("approve", approve.status_code, approve.json())
        assert approve.status_code == 200

        done = _wait_status(client, job_id, {"DONE"})
        print("done", done)
        assert done["approval"] == "approved"
        assert done["current_agent"] == "writer"

        # Rechazo
        rejected_create = client.post("/tasks", json={"task": "Probar rechazo HITL"})
        rejected_id = rejected_create.json()["job_id"]
        _wait_status(client, rejected_id, {"AWAITING_APPROVAL"})
        client.post(f"/tasks/{rejected_id}/approve", json={"approved": False})
        rejected = _wait_status(client, rejected_id, {"DONE"})
        print("rejected", rejected)
        assert rejected["approval"] == "rejected"

    print("ALL OK")


if __name__ == "__main__":
    main()
