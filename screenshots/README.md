# Capturas del dashboard de observabilidad

Guardá acá una captura del dashboard tras ejecutar al menos un job.

## LangSmith (recomendado)

1. En `.env`:
   ```env
   OBSERVABILITY_BACKEND=langsmith
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=tu_key
   LANGCHAIN_PROJECT=async-multi-agent-api-monitoring
   ```
2. Levantá la API y encolá una tarea: `POST /tasks`
3. Abrí https://smith.langchain.com → proyecto → trace del job (`job-<id>`)
4. Guardá la captura como `langsmith-traces.png` en esta carpeta

## Phoenix (opcional)

1. `pip install arize-phoenix openinference-instrumentation-langchain`
2. `phoenix serve` (UI en http://localhost:6006)
3. En `.env`: `OBSERVABILITY_BACKEND=phoenix` y `PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006`
4. Ejecutá un job y capturá el dashboard como `phoenix-traces.png`
