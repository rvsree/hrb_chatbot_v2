"""Tests for the Phase 61 scaffold (ai/agents/workflow_agents/
multi_agent_pipeline.py) - confirms each step raises NotImplementedError
naming a real file, not a generic message."""

import pytest

from src.hrb_chatbot.ai.agents.workflow_agents import multi_agent_pipeline


def test_route_query_names_the_orchestrator_router_file():
    with pytest.raises(NotImplementedError) as exc_info:
        multi_agent_pipeline.route_query("test query")

    assert "orchestrator_router.py" in str(exc_info.value)


async def test_run_multi_agent_surfaces_route_query_not_implemented():
    with pytest.raises(NotImplementedError):
        await multi_agent_pipeline.run_multi_agent("test query", employee_id="EMP052")
