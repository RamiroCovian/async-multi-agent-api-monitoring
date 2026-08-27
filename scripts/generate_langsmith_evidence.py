"""Genera una traza en LangSmith y muestra el link al dashboard.

Uso:
  1. Copiá .env.example → .env y configurá LANGCHAIN_API_KEY
  2. docker compose up -d redis
  3. PYTHONPATH=. python scripts/generate_langsmith_evidence.py

Luego abrí el link, capturá el dashboard y guardá:
  screenshots/langsmith-traces.png
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Forzar tracing antes de importar la app
os.environ.setdefault("OBSERVABILITY_BACKEND", "langsmith")
os.environ["LANGCHAIN_TRACING_V2"] = "true"

if not os.getenv("LANGCHAIN_API_KEY"):
    print("ERROR: Falta LANGCHAIN_API_KEY en .env")
    print("Obtené una en https://smith.langchain.com -> Settings -> API Keys")
    sys.exit(1)

PROJECT = os.getenv("LANGCHAIN_PROJECT", "async-multi-agent-api-monitoring")


def _wait_status(client, job_id: str, wanted: set[str], timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        body = client.get(f"/tasks/{job_id}").json()
        status = body.get("status")
        if status == "AWAITING_APPROVAL":
            client.post(f"/tasks/{job_id}/approve", json={"approved": True})
        elif status in wanted:
            return body
        time.sleep(0.2)
    raise TimeoutError(f"timeout job {job_id}: {body}")


def _print_langsmith_links() -> None:
    try:
        from langsmith import Client

        client = Client()
        runs = list(
            client.list_runs(
                project_name=PROJECT,
                limit=5,
                is_root=True,
            )
        )
        if not runs:
            print("\nNo se encontraron runs aún. Esperá unos segundos y revisá:")
            print(f"  https://smith.langchain.com → proyecto '{PROJECT}'")
            return

        print("\n=== Trazas recientes en LangSmith ===")
        for run in runs[:3]:
            url = client.get_run_url(run=run)
            print(f"- {run.name}: {url}")

        print(f"\nProyecto: https://smith.langchain.com (buscá '{PROJECT}')")
        print("\nCapturá la pantalla del trace y guardala como:")
        print("  screenshots/langsmith-traces.png")
    except Exception as exc:
        print(f"\nNo pude listar runs automáticamente: {exc}")
        print(f"Abrí manualmente: https://smith.langchain.com → '{PROJECT}'")


def main() -> None:
    from fastapi.testclient import TestClient

    from app.observability import configure_observability

    configure_observability()

    print(f"Proyecto LangSmith: {PROJECT}")
    print("Ejecutando job con trazas (planner -> HITL -> writer)...\n")

    with TestClient(app := __import__("app.main", fromlist=["app"]).app) as client:
        health = client.get("/health")
        print("health", health.json())

        created = client.post(
            "/tasks",
            json={"task": "Evidencia pre-entrega: trazas LangSmith multiagente"},
        )
        created.raise_for_status()
        job_id = created.json()["job_id"]
        print("job_id", job_id)

        done = _wait_status(client, job_id, {"DONE"})
        print("status", done["status"], "| agent", done.get("current_agent"))

    print("\nEsperando que LangSmith indexe la traza…")
    time.sleep(3)
    _print_langsmith_links()
    print("\nListo.")


if __name__ == "__main__":
    main()
