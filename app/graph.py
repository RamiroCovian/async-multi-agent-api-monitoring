"""Orquestador multiagente (LangGraph) con checkpointer RedisSaver.

Pipeline M6:
  planner -> researcher -> analyst -> writer

El checkpointer Redis persiste el estado por `thread_id` (p. ej. job_id).
El nodo HITL / interrupt se agrega en feature/20260827_hitl.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.llm import get_chat_model, has_llm_credentials


class AgentState(TypedDict):
    """Estado compartido del grafo multiagente."""

    task: str
    plan: str
    research: str
    analysis: str
    result: str
    current_agent: str


def _llm_invoke(system: str, user: str) -> str:
    """Invoca el LLM del provider activo; sin key responde en modo stub."""
    if not has_llm_credentials():
        return f"[stub] {system.split('.')[0]} :: {user[:200]}"

    llm = get_chat_model()
    response = llm.invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return str(response.content)


def planner_node(state: AgentState) -> dict[str, str]:
    """Agente planificador: descompone la tarea en pasos."""
    plan = _llm_invoke(
        "Sos un planificador. Devolvé un plan breve en pasos numerados.",
        f"Tarea: {state['task']}",
    )
    return {"plan": plan, "current_agent": "planner"}


def researcher_node(state: AgentState) -> dict[str, str]:
    """Agente investigador: reúne hallazgos según el plan."""
    research = _llm_invoke(
        "Sos un investigador. Resumí hallazgos clave y fuentes conceptuales.",
        f"Tarea: {state['task']}\nPlan:\n{state['plan']}",
    )
    return {"research": research, "current_agent": "researcher"}


def analyst_node(state: AgentState) -> dict[str, str]:
    """Agente analista: interpreta la investigación."""
    analysis = _llm_invoke(
        "Sos un analista. Extraé insights, riesgos y recomendaciones.",
        (
            f"Tarea: {state['task']}\n"
            f"Plan:\n{state['plan']}\n"
            f"Investigación:\n{state['research']}"
        ),
    )
    return {"analysis": analysis, "current_agent": "analyst"}


def writer_node(state: AgentState) -> dict[str, str]:
    """Agente redactor: produce el resultado final."""
    result = _llm_invoke(
        "Sos un redactor técnico. Escribí una respuesta clara y accionable.",
        (
            f"Tarea: {state['task']}\n"
            f"Análisis:\n{state['analysis']}\n"
            f"Investigación:\n{state['research']}"
        ),
    )
    return {"result": result, "current_agent": "writer"}


def create_checkpointer(redis_url: str | None = None) -> RedisSaver:
    """Crea y prepara RedisSaver (índices RediSearch).

    Args:
        redis_url: URL de Redis. Por defecto usa Settings.redis_url.

    Returns:
        Checkpointer listo para compilar el grafo.
    """
    url = redis_url or get_settings().redis_url
    checkpointer = RedisSaver(redis_url=url)
    checkpointer.setup()
    return checkpointer


def build_graph(checkpointer: RedisSaver | None = None) -> CompiledStateGraph:
    """Compila el grafo multiagente con checkpointer Redis.

    Args:
        checkpointer: RedisSaver ya configurado. Si es None, se crea uno nuevo.

    Returns:
        Grafo compilado listo para `invoke` / `ainvoke`.
    """
    saver = checkpointer or create_checkpointer()

    builder: StateGraph = StateGraph(AgentState)
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("writer", writer_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "analyst")
    builder.add_edge("analyst", "writer")
    builder.add_edge("writer", END)

    return builder.compile(checkpointer=saver)


def run_graph(
    task: str,
    *,
    thread_id: str,
    checkpointer: RedisSaver | None = None,
) -> dict[str, Any]:
    """Ejecuta el grafo para una tarea persistiendo checkpoints en Redis.

    Args:
        task: Descripción de la tarea.
        thread_id: ID de hilo (típicamente el job_id de la API).
        checkpointer: RedisSaver opcional (reutilizar en worker).

    Returns:
        Estado final del grafo.
    """
    graph = build_graph(checkpointer=checkpointer)
    initial: AgentState = {
        "task": task,
        "plan": "",
        "research": "",
        "analysis": "",
        "result": "",
        "current_agent": "",
    }
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial, config=config)
