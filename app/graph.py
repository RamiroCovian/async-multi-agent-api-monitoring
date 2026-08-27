"""Orquestador multiagente (LangGraph) con checkpointer RedisSaver.

Pipeline M6:
  planner -> researcher -> analyst -> human_approval (HITL) -> writer

El checkpointer Redis persiste el estado por `thread_id` (p. ej. job_id).
El nodo `human_approval` usa `interrupt()` y se reanuda vía POST /tasks/{id}/approve.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.redis import RedisSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from app.config import get_settings
from app.llm import get_chat_model, has_llm_credentials
from app.observability import graph_run_config, trace_agent_node


class AgentState(TypedDict):
    """Estado compartido del grafo multiagente."""

    task: str
    plan: str
    research: str
    analysis: str
    result: str
    current_agent: str
    approval: str


def _llm_invoke(system: str, user: str, *, agent_name: str = "agent") -> str:
    """Invoca el LLM del provider activo; sin key responde en modo stub."""

    def _run() -> str:
        if not has_llm_credentials():
            return f"[stub] {system.split('.')[0]} :: {user[:200]}"

        llm = get_chat_model()
        response = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return str(response.content)

    if get_settings().observability_backend == "none":
        return _run()

    try:
        from langsmith import traceable

        traced = traceable(
            name=f"{agent_name}_llm",
            run_type="llm",
            metadata={"agent": agent_name},
        )(_run)
        return traced()
    except Exception:
        return _run()


@trace_agent_node("planner")
def planner_node(state: AgentState) -> dict[str, str]:
    """Agente planificador: descompone la tarea en pasos."""
    plan = _llm_invoke(
        "Sos un planificador. Devolvé un plan breve en pasos numerados.",
        f"Tarea: {state['task']}",
        agent_name="planner",
    )
    return {"plan": plan, "current_agent": "planner"}


@trace_agent_node("researcher")
def researcher_node(state: AgentState) -> dict[str, str]:
    """Agente investigador: reúne hallazgos según el plan."""
    research = _llm_invoke(
        "Sos un investigador. Resumí hallazgos clave y fuentes conceptuales.",
        f"Tarea: {state['task']}\nPlan:\n{state['plan']}",
        agent_name="researcher",
    )
    return {"research": research, "current_agent": "researcher"}


@trace_agent_node("analyst")
def analyst_node(state: AgentState) -> dict[str, str]:
    """Agente analista: interpreta la investigación."""
    analysis = _llm_invoke(
        "Sos un analista. Extraé insights, riesgos y recomendaciones.",
        (
            f"Tarea: {state['task']}\n"
            f"Plan:\n{state['plan']}\n"
            f"Investigación:\n{state['research']}"
        ),
        agent_name="analyst",
    )
    return {"analysis": analysis, "current_agent": "analyst"}


@trace_agent_node("human_approval")
def human_approval_node(state: AgentState) -> dict[str, str]:
    """Pausa obligatoria para aprobación humana antes del writer."""
    decision = interrupt(
        {
            "type": "human_approval",
            "message": "Aprobación humana requerida antes de redactar el resultado final.",
            "task": state["task"],
            "analysis_preview": (state.get("analysis") or "")[:500],
        }
    )
    normalized = str(decision).strip().lower()
    if normalized in {"rejected", "reject", "no", "false", "0"}:
        return {
            "approval": "rejected",
            "current_agent": "human_approval",
            "result": "Tarea rechazada por aprobador humano.",
        }
    return {"approval": "approved", "current_agent": "human_approval"}


def route_after_approval(state: AgentState) -> str:
    """Si se rechaza, termina; si se aprueba, continúa al writer."""
    if state.get("approval") == "rejected":
        return END
    return "writer"


@trace_agent_node("writer")
def writer_node(state: AgentState) -> dict[str, str]:
    """Agente redactor: produce el resultado final."""
    result = _llm_invoke(
        "Sos un redactor técnico. Escribí una respuesta clara y accionable.",
        (
            f"Tarea: {state['task']}\n"
            f"Análisis:\n{state['analysis']}\n"
            f"Investigación:\n{state['research']}"
        ),
        agent_name="writer",
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
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("writer", writer_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "analyst")
    builder.add_edge("analyst", "human_approval")
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {"writer": "writer", END: END},
    )
    builder.add_edge("writer", END)

    return builder.compile(checkpointer=saver)


def _initial_state(task: str) -> AgentState:
    return {
        "task": task,
        "plan": "",
        "research": "",
        "analysis": "",
        "result": "",
        "current_agent": "",
        "approval": "",
    }


def _result_from_interrupt(
    graph: CompiledStateGraph,
    config: dict[str, Any],
    *,
    initial: AgentState | None = None,
    invoke_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normaliza el estado cuando el grafo queda pausado en HITL."""
    if invoke_result and "__interrupt__" in invoke_result:
        values = {k: v for k, v in invoke_result.items() if not k.startswith("__")}
    else:
        snapshot = graph.get_state(config)
        values = dict(snapshot.values) if snapshot.values else dict(initial or {})
    values["__interrupted__"] = True
    return values


def _is_interrupted(result: dict[str, Any]) -> bool:
    return bool(result.get("__interrupted__") or result.get("__interrupt__"))


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
    initial = _initial_state(task)
    config = graph_run_config(thread_id=thread_id, task=task)
    try:
        result = graph.invoke(initial, config=config)
        if _is_interrupted(result):
            return _result_from_interrupt(graph, config, initial=initial, invoke_result=result)
        return result
    except GraphInterrupt:
        return _result_from_interrupt(graph, config, initial=initial)


def resume_graph(
    thread_id: str,
    *,
    approved: bool,
    checkpointer: RedisSaver | None = None,
) -> dict[str, Any]:
    """Reanuda el grafo tras aprobación humana (Command(resume=...))."""
    graph = build_graph(checkpointer=checkpointer)
    config = graph_run_config(thread_id=thread_id, task="")
    resume_value = "approved" if approved else "rejected"
    try:
        result = graph.invoke(Command(resume=resume_value), config=config)
        if _is_interrupted(result):
            return _result_from_interrupt(graph, config, invoke_result=result)
        return result
    except GraphInterrupt:
        return _result_from_interrupt(graph, config)
