"""Multi-agentic-rag's real LangGraph graph (Phase 64): Planner Agent ->
Orchestration Agent dispatch (Send fan-out) -> 4 domain agents in parallel ->
Reviewer Agent. Hierarchical/LangGraph-supervisor pattern, per the user's
explicit, final direction - not Azure's flat single-agent-many-tools pattern."""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.hrb_chatbot.ai.agents.domain_agents import (
    lms_analytics_agent,
    lms_ops_agent,
    sql_db_agent,
    vector_kb_agent,
    web_search_agent,
)
from src.hrb_chatbot.ai.agents.workflow_agents import planner_agent, reviewer_agent
from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.ai.pre_processing.guardrails_input import check_input
from src.hrb_chatbot.ai.rag_pipeline.response_generation.guardrails_output import check_output
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("agents.multi_agent_pipeline")

DOMAIN_AGENT_NODES = [
    "vector_kb_agent",
    "lms_ops_agent",
    "sql_db_agent",
    "lms_analytics_agent",
    "web_search_agent",
]


class MultiAgentState(TypedDict):
    query: str
    employee_id: str | None
    tasks: list[dict]
    agent_results: Annotated[list[dict], operator.add]
    answer: str


async def planner_node(state: MultiAgentState) -> dict:
    tasks = await planner_agent.plan(state["query"])
    return {"tasks": tasks}


def dispatch_to_agents(state: MultiAgentState) -> list[Send]:
    """The Orchestration Agent's dispatch step - fans each task out to its domain
    agent in parallel via LangGraph's own Send() API, not asyncio.gather()."""
    return [
        Send(task["agent"], {"query": state["query"], "employee_id": state["employee_id"], "focus": task["focus"]})
        for task in state["tasks"]
    ]


async def vector_kb_agent_node(state: dict) -> dict:
    result = await vector_kb_agent.run(state["focus"])
    return {"agent_results": [{"agent": "vector_kb_agent", "focus": state["focus"], "result": result}]}


async def lms_ops_agent_node(state: dict) -> dict:
    result = await lms_ops_agent.run(state["focus"], state["employee_id"])
    return {"agent_results": [{"agent": "lms_ops_agent", "focus": state["focus"], "result": result}]}


async def sql_db_agent_node(state: dict) -> dict:
    result = await sql_db_agent.run(state["focus"])
    return {"agent_results": [{"agent": "sql_db_agent", "focus": state["focus"], "result": result}]}


async def lms_analytics_agent_node(state: dict) -> dict:
    result = await lms_analytics_agent.run(state["focus"])
    return {"agent_results": [{"agent": "lms_analytics_agent", "focus": state["focus"], "result": result}]}


async def web_search_agent_node(state: dict) -> dict:
    result = await web_search_agent.run(state["focus"])
    return {"agent_results": [{"agent": "web_search_agent", "focus": state["focus"], "result": result}]}


async def reviewer_node(state: MultiAgentState) -> dict:
    answer = await reviewer_agent.review(state["query"], state["agent_results"])
    return {"answer": answer}


def _build_graph():
    graph = StateGraph(MultiAgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("vector_kb_agent", vector_kb_agent_node)
    graph.add_node("lms_ops_agent", lms_ops_agent_node)
    graph.add_node("sql_db_agent", sql_db_agent_node)
    graph.add_node("lms_analytics_agent", lms_analytics_agent_node)
    graph.add_node("web_search_agent", web_search_agent_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", dispatch_to_agents, DOMAIN_AGENT_NODES)
    for node_name in DOMAIN_AGENT_NODES:
        graph.add_edge(node_name, "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile()


_GRAPH = None


def get_graph():
    """Builds the compiled graph once and reuses it - same lazy-singleton shape as this project's client gateways."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


async def run_multi_agent(
    query: str,
    employee_id: str | None,
    enable_conversation_memory: bool = False,
    conversation_id: str | None = None,
) -> dict:
    """Runs the Planner -> Orchestration -> domain agents -> Reviewer graph for one query.
    Guardrails run here, same layer as genai-rag's pipeline.answer_query() - the route
    (api/multi_agentic_rag/query_agent.py) only catches GuardrailBlockedError."""
    checked_query = await check_input(query)

    resolved_conversation_id = None
    if enable_conversation_memory:
        resolved_conversation_id = conversation_id or conversation_memory.new_conversation_id()

    graph = get_graph()
    final_state = await graph.ainvoke(
        {"query": checked_query, "employee_id": employee_id, "tasks": [], "agent_results": [], "answer": ""}
    )

    answer = await check_output(checked_query, final_state["answer"])
    if resolved_conversation_id:
        conversation_memory.save_turn(resolved_conversation_id, checked_query, answer)

    agent_results = final_state["agent_results"]
    tools_used = [{"tool_name": result["agent"], "tool_input": result["focus"]} for result in agent_results]

    return {
        "answer": answer,
        "tasks": final_state["tasks"],
        "tools_used": tools_used,
        # Raw per-domain-agent result text, kept alongside tools_used - needed to eval
        # groundedness against what was actually retrieved (Phase 69), not just the final answer.
        "agent_result_texts": [result["result"] for result in agent_results],
        "iterations": len(agent_results),
        "conversation_id": resolved_conversation_id,
    }
