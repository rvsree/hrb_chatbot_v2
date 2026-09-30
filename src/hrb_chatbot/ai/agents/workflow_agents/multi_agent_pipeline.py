"""Phase 61 scaffold, not an implementation - each step below names the
file and phase that will fill it in, same pattern as Phase 3/5's own
stubbed pipelines. See docs/dev-reference/react_agents/ for the design
document that will settle how these steps actually work."""


def route_query(query: str) -> list[dict]:
    """Classify one query into one or more sub-agent tasks."""
    raise NotImplementedError(
        "route_query() is not implemented yet - see "
        "ai/agents/workflow_agents/orchestrator_router.py and the design document in "
        "docs/dev-reference/react_agents/ for the routing approach to build here."
    )


async def dispatch_to_agents(tasks: list[dict], employee_id: str | None) -> list[dict]:
    """Run each task's sub-agent - concurrently, once a reuse strategy is chosen."""
    raise NotImplementedError(
        "dispatch_to_agents() is not implemented yet - see ai/agents/domain_agents/ "
        "and the design document in docs/dev-reference/react_agents/ for how sub-agents "
        "reuse ai/agents/workflow_agents/orchestration_agent.py's existing tool-calling loop."
    )


def synthesize_results(query: str, agent_results: list[dict]) -> str:
    """Merge every sub-agent's result into one final answer."""
    raise NotImplementedError(
        "synthesize_results() is not implemented yet - see "
        "ai/agents/workflow_agents/synthesizer.py and the design document in "
        "docs/dev-reference/react_agents/ for the merge approach to build here."
    )


async def run_multi_agent(query: str, employee_id: str | None) -> dict:
    """Orchestrates one multi-agent query: route, dispatch, synthesize."""
    tasks = route_query(query)
    agent_results = await dispatch_to_agents(tasks, employee_id)
    answer = synthesize_results(query, agent_results)
    return {"answer": answer, "tasks": tasks, "tools_used": [], "iterations": 0}
