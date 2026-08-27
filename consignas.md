# Pre-entrega 7: API de producción y monitoreo activo

## Qué construir

API REST (FastAPI) que exponga el sistema multi-agente del Módulo 6, con:

1. **Endpoints asíncronos** — recibir tarea, encolar, devolver `job_id` (sin bloquear).
2. **Estado en Redis** — jobs + checkpoints de LangGraph (`RedisSaver` o similar).
3. **Observabilidad** — trazas por ejecución (LangSmith o Arize Phoenix / OpenInference).
4. **HITL** — pausa obligatoria para aprobación humana en tareas críticas.

## Pasos sugeridos

1. **Refactorización del grafo** — orquestador M6 + Redis checkpointer + interrupt en nodo/arista crítica.
2. **Wrappers de observabilidad** — env vars LangSmith o colector Phoenix; decorar llamadas a LLM.
3. **Arquitectura de la API** — FastAPI + worker (thread async, Celery o Arq).
4. **Pruebas de carga** — 5 peticiones concurrentes; verificar trazas y latencia en el dashboard.

## Errores comunes a evitar

- **Bloquear el event loop** — no hacer sync a DB/LLM en endpoints sin `run_in_threadpool` o async nativo.
- **Errores en background tasks** — si el agente falla, capturar excepción y marcar estado `FAILED` en Redis.

---

## Qué entregás

| | |
|---|---|
| **Tipo** | Código — repo de GitHub |
| **Artefacto** | API FastAPI async, Redis, observabilidad, HITL, `requirements.txt`, Docker Compose (opcional), capturas del dashboard |
| **No hace falta** | Documento/informe; las capturas son la evidencia |

### Estructura de referencia

```text
mi-api-agente/
├── app/
│   ├── main.py           # POST /tasks · GET /tasks/{id}
│   ├── graph.py          # orquestador M6 + RedisSaver
│   ├── worker.py         # PENDING / RUNNING / FAILED / DONE
│   ├── observability.py  # Phoenix o LangSmith
│   └── hitl.py           # interrupt + POST /tasks/{id}/approve
├── requirements.txt
├── docker-compose.yml    # (opcional) app + redis
├── .env.example
├── screenshots/
└── README.md
```

### Checklist de entrega (rúbrica)

| Criterio | Peso |
|---|---|
| Endpoint async → `job_id` sin bloquear event loop | 30% |
| Estado en Redis (incluye `FAILED` ante excepción) | 25% |
| Trazas en dashboard + captura en `/screenshots` | 20% |
| Nodo HITL hasta aprobación externa | 15% |
| README + `requirements.txt` | 10% |

Repo público: probar `git clone` en limpio antes de entregar.

---

## Plan de branches

Prefijo: `feature/20260827_`

Cada feature = 1 branch → PR a `main`. Orden sugerido (dependencias de arriba hacia abajo):

| # | Branch | Qué incluye | Criterio rúbrica |
|---|---|---|---|
| 1 | `feature/20260827_scaffold` | Estructura `app/`, `requirements.txt`, `.env.example`, Docker Compose (Redis), esqueleto FastAPI | Docs/estructura (parcial) |
| 2 | `feature/20260827_redis-graph` | Grafo multi-agente M6 + `RedisSaver` / checkpointer | Persistencia Redis |
| 3 | `feature/20260827_async-api` | `POST /tasks`, `GET /tasks/{id}`, worker, estados PENDING/RUNNING/FAILED/DONE | Orquestación async + API |
| 4 | `feature/20260827_observability` | LangSmith o Phoenix, decoradores de trazas, `/screenshots` | Observabilidad |
| 5 | `feature/20260827_hitl` | Nodo de aprobación + `POST /tasks/{id}/approve` | HITL |
| 6 | `feature/20260827_docs` | README (Redis + API + 5 requests concurrentes), pulido final | Documentación |

### Flujo de trabajo

```bash
git checkout main
git pull
git checkout -b feature/20260827_<nombre>
# ... implementar ...
git push -u origin HEAD
# abrir PR → merge a main → siguiente feature
```

### Notas

- Mergear en orden 1 → 6 para evitar conflictos grandes.
- Observabilidad y HITL pueden ir en paralelo *después* de `async-api` si se coordinan bien; lo más seguro es secuencial.
- Capturas del dashboard van en la branch de observabilidad (o en `docs` si se hacen al final).
