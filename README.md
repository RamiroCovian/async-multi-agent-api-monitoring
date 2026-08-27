# async-multi-agent-api-monitoring

API REST asíncrona para un sistema multiagente (FastAPI + LangGraph) con jobs y checkpoints en Redis, observabilidad (LangSmith) y aprobación humana (HITL) en tareas críticas.

## Arquitectura

```text
Cliente → POST /tasks (202 + job_id)
              ↓
         Background worker (threadpool)
              ↓
    LangGraph: planner → researcher → analyst → human_approval → writer
              ↓                              ↑ interrupt
         Redis (jobs + RedisSaver)     POST /tasks/{id}/approve
              ↓
         LangSmith (trazas opcionales)
```

## Estructura del repo

```text
app/
├── main.py            # FastAPI: /health, /tasks, lifespan
├── graph.py           # Orquestador multiagente + RedisSaver + HITL interrupt
├── worker.py          # PENDING / RUNNING / AWAITING_APPROVAL / DONE / FAILED
├── jobs.py            # Estado operativo de jobs en Redis
├── hitl.py            # POST /tasks/{id}/approve
├── observability.py   # LangSmith / Phoenix
├── llm.py             # Multi-provider: gemini | openai | anthropic
├── config.py          # Settings desde .env
└── schemas.py         # Modelos Pydantic
scripts/
├── smoke_tasks.py           # Smoke DONE + FAILED
├── smoke_hitl.py            # Smoke HITL approve/reject
└── load_test_concurrent.py  # 5 requests concurrentes
screenshots/                 # Capturas del dashboard (ver screenshots/README.md)
```

## Requisitos

- Python 3.12+
- Docker (Redis 8 con RediSearch/RedisJSON)
- API key del LLM elegido (opcional: sin key corre en modo stub)

## Setup

```bash
python -m venv env

# Windows
.\env\Scripts\activate
# Linux / macOS
# source env/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### Variables de entorno (`.env`)

| Variable | Descripción |
|---|---|
| `REDIS_URL` | Redis local (`redis://localhost:6380/0`) |
| `LLM_PROVIDER` | `gemini` \| `openai` \| `anthropic` |
| `GOOGLE_API_KEY` | Key de Gemini (si `LLM_PROVIDER=gemini`) |
| `OBSERVABILITY_BACKEND` | `langsmith` \| `phoenix` \| `none` |
| `LANGCHAIN_TRACING_V2` | `true` para enviar trazas a LangSmith |
| `LANGCHAIN_API_KEY` | API key de LangSmith |

### Redis

```bash
docker compose up -d redis
```

Redis queda en **localhost:6380** (mapeo host→contenedor). Requiere Redis 8+ por `RedisSaver` (RediSearch + RedisJSON).

Verificar:

```bash
docker compose ps
docker exec ama-redis redis-cli INFO modules
```

### API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Docs interactivas: http://localhost:8000/docs

## API

### `GET /health`

```json
{"status": "ok", "tracing_enabled": false}
```

### `POST /tasks` → `202`

Encola la tarea y devuelve `job_id` sin bloquear el event loop.

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d "{\"task\":\"Analizar APIs async\"}"
```

```json
{"job_id": "uuid", "status": "PENDING"}
```

### `GET /tasks/{job_id}`

Estados: `PENDING` → `RUNNING` → `AWAITING_APPROVAL` → `DONE` | `FAILED`

```bash
curl http://localhost:8000/tasks/<job_id>
```

### `POST /tasks/{job_id}/approve` (HITL)

Cuando `status=AWAITING_APPROVAL`, aprobar o rechazar:

```bash
curl -X POST http://localhost:8000/tasks/<job_id>/approve \
  -H "Content-Type: application/json" \
  -d "{\"approved\":true}"
```

- `approved: true` → continúa al agente `writer` → `DONE`
- `approved: false` → `DONE` con mensaje de rechazo

## Prueba de carga (5 requests concurrentes)

Con la API y Redis levantados:

```bash
# Windows (venv activado)
$env:PYTHONPATH = (Get-Location).Path
python scripts/load_test_concurrent.py

# Linux / macOS
PYTHONPATH=. python scripts/load_test_concurrent.py
```

Opciones:

```bash
python scripts/load_test_concurrent.py --concurrency 5 --base-url http://localhost:8000
```

El script mide latencia de `POST` (debe ser baja, ~ms) y tiempo total hasta `DONE` (incluye HITL auto-aprobado). Revisá trazas en LangSmith si `LANGCHAIN_TRACING_V2=true`.

## Observabilidad (LangSmith)

```env
OBSERVABILITY_BACKEND=langsmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=tu_key
LANGCHAIN_PROJECT=async-multi-agent-api-monitoring
```

Tras ejecutar jobs, las trazas aparecen en [smith.langchain.com](https://smith.langchain.com) con tags `multi-agent`, `api` y `job_id` en metadata.

Capturas: guardar en `screenshots/` (ver `screenshots/README.md`).

## Smoke tests

```bash
PYTHONPATH=. python scripts/smoke_tasks.py
PYTHONPATH=. python scripts/smoke_hitl.py
```

## Docker (API + Redis)

```bash
cp .env.example .env
# Ajustar REDIS_URL=redis://redis:6379/0 si corre todo en Docker
docker compose --profile full up -d
```

## Checklist de entrega

- [ ] `git clone` limpio + `pip install -r requirements.txt`
- [ ] `docker compose up -d redis` + API en `:8000`
- [ ] `POST /tasks` devuelve `202` + `job_id` al instante
- [ ] Jobs persisten estado en Redis (`DONE` / `FAILED` / `AWAITING_APPROVAL`)
- [ ] HITL: approve → continúa; reject → rechazo
- [ ] Trazas visibles en LangSmith + captura en `screenshots/`
- [ ] `load_test_concurrent.py` con 5 requests OK
