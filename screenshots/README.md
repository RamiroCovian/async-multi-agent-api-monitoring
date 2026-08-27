# Capturas del dashboard de observabilidad

Guardá acá la **captura real** del dashboard (requerido para la rúbrica).

## Guía rápida — LangSmith

### 1. Configurar `.env`

```bash
cp .env.example .env
```

Editá `.env`:

```env
OBSERVABILITY_BACKEND=langsmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...          # https://smith.langchain.com → Settings → API Keys
LANGCHAIN_PROJECT=async-multi-agent-api-monitoring

# Opcional: tu LLM (sin key corre en stub)
LLM_PROVIDER=gemini
GOOGLE_API_KEY=tu_key_gemini
```

### 2. Generar traza automáticamente

```bash
docker compose up -d redis

# Windows
$env:PYTHONPATH = (Get-Location).Path
python scripts/generate_langsmith_evidence.py

# Linux / macOS
PYTHONPATH=. python scripts/generate_langsmith_evidence.py
```

El script imprime links directos a las trazas en LangSmith.

### 3. Tomar la captura

1. Abrí el link que imprime el script (o https://smith.langchain.com → proyecto `async-multi-agent-api-monitoring`)
2. Entrá al trace del job (`job-<id>` o nombre con `planner` / `human_approval`)
3. Capturá pantalla mostrando el árbol de nodos multiagente
4. Guardá como **`langsmith-traces.png`** en esta carpeta

### 4. Commitear la evidencia

```bash
git add screenshots/langsmith-traces.png
git commit -m "docs: captura dashboard LangSmith pre-entrega"
git push
```

## Qué debe verse en la captura

- Proyecto `async-multi-agent-api-monitoring`
- Trace de un job con nodos: `planner`, `researcher`, `analyst`, `human_approval`, `writer`
- Tags `multi-agent` / `api` (opcional pero suma)

## Phoenix (alternativa)

Solo si preferís Phoenix en lugar de LangSmith:

```bash
pip install arize-phoenix openinference-instrumentation-langchain
phoenix serve
```

`.env`:

```env
OBSERVABILITY_BACKEND=phoenix
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

Captura → `screenshots/phoenix-traces.png`
