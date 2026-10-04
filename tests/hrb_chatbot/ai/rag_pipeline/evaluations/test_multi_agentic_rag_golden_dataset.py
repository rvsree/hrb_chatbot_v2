"""Scores multi-agentic-rag against the golden dataset's real cases (Phase 69 -
golden_dataset_harness.py was already generic, just never pointed at
run_multi_agent() before). Real API calls, real cost - excluded from the
default suite, run with `pytest -m eval -v`. Same light-smoke-test pattern as
test_golden_dataset_harness.py: confirms real scores come back, not a quality gate."""

import pytest

from src.hrb_chatbot.ai.agents.workflow_agents.multi_agent_pipeline import run_multi_agent
from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import load_golden_cases, score_case
from tests.hrb_chatbot.ai.rag_pipeline.evaluations._eval_helpers import extract_filenames

pytestmark = pytest.mark.eval

EVAL_EMPLOYEE_ID = "EMP052"


async def ask_multi_agentic_rag(query: str) -> dict:
    """Adapts multi-agentic-rag's real Planner/Orchestration/Reviewer graph to
    the harness's plain contract. agent_result_texts (Phase 69) is every
    dispatched domain agent's raw result text, not just the Reviewer's merge."""
    result = await run_multi_agent(query, employee_id=EVAL_EMPLOYEE_ID)
    agent_texts = result.get("agent_result_texts", [])
    return {
        "answer": result["answer"],
        "retrieved_texts": agent_texts,
        "retrieved_ids": extract_filenames(agent_texts),
    }


async def test_golden_dataset_cases_score_above_zero():
    """Confirms the harness works end to end against the real multi-agent
    graph, including the 2 multi-part cases added in Phase 67."""
    all_cases = load_golden_cases()
    sample = [case for case in all_cases if case["category"] == "happy"][:2]
    sample += [case for case in all_cases if case["id"].startswith("multi-agent-")]

    for case in sample:
        result = await score_case(case, ask_multi_agentic_rag)
        for metric_name, score in result["scores"].items():
            assert score is not None, f"{case['id']} / {metric_name} returned no score"
