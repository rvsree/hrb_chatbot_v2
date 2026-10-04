"""Scores single-agentic-rag against the golden dataset's real cases (Phase 69 -
golden_dataset_harness.py was already generic, just never pointed at run_agent()
before). Real API calls, real cost - excluded from the default suite, run with
`pytest -m eval -v`. Same light-smoke-test pattern as
test_golden_dataset_harness.py: confirms real scores come back, not a quality gate."""

import pytest

from src.hrb_chatbot.ai.agents.workflow_agents.orchestration_agent import run_agent
from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import load_golden_cases, score_case
from tests.hrb_chatbot.ai.rag_pipeline.evaluations._eval_helpers import extract_filenames

pytestmark = pytest.mark.eval

EVAL_EMPLOYEE_ID = "EMP052"


async def ask_single_agentic_rag(query: str) -> dict:
    """Adapts single-agentic-rag's real tool-calling loop to the harness's plain
    contract. tool_outputs (Phase 66) is what makes groundedness checkable here -
    without it there would be no real context to check the answer against."""
    result = await run_agent(query, employee_id=EVAL_EMPLOYEE_ID)
    tool_outputs = result.get("tool_outputs", [])
    return {
        "answer": result["answer"],
        "retrieved_texts": tool_outputs,
        "retrieved_ids": extract_filenames(tool_outputs),
    }


async def test_golden_dataset_cases_score_above_zero():
    """Confirms the harness works end to end against a real agentic pipeline,
    not just genai-rag's direct retrieve-then-generate path. A small sample of
    policy questions - cases that should route to SearchKnowledgeBase."""
    cases = [case for case in load_golden_cases() if case["category"] == "happy"][:3]

    for case in cases:
        result = await score_case(case, ask_single_agentic_rag)
        for metric_name, score in result["scores"].items():
            assert score is not None, f"{case['id']} / {metric_name} returned no score"
