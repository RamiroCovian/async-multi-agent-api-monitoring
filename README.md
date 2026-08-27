# async-multi-agent-api-monitoring

API REST asíncrona para un sistema multiagente desarrollado con FastAPI y LangGraph, con gestión de trabajos y checkpoints en Redis, observabilidad mediante LangSmith y aprobación humana para tareas críticas.

## Estructura

```text
app/
├── main.py            # POST /tasks · GET /tasks/{id} · GET /health
├── graph.py           # orquestador LangGraph + RedisSaver
├── worker.py          # PENDING / RUNNING / FAILED / DONE
├── observability.py   # LangSmith o Phoenix
└── hitl.py            # interrupt + POST /tasks/{id}/approve
```

## Setup rápido

```bash
# Entorno virtual
python -m venv env
# Windows
.\env\Scripts\activate
# Linux / macOS
# source env/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Redis (solo Redis; la API corre en local)
docker compose up -d redis

# API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET http://localhost:8000/health`

Para levantar API + Redis con Docker: `docker compose --profile full up -d` (requiere `.env`).
