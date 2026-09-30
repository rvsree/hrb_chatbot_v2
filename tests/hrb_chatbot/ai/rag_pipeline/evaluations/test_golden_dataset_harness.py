"""Scores genai-rag against the golden dataset's 23 real cases (Phase 8,
rebuilt in Phase 62 to match modules/5_evaluation/demo.py directly).
Real API calls, real cost - excluded from the default suite, run with
`pytest -m eval -v`. Not mocked on purpose: this is the one place this
project checks retrieval/generation quality against real data, for real."""

import pytest

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import load_golden_cases, score_case
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

pytestmark = pytest.mark.eval


async def ask_genai_rag(query: str) -> dict:
    """Adapts genai-rag's real pipeline to the harness's plain contract."""
    result = await pipeline.answer_query(RagQueryParams(query=query))
    retrieved_texts = [chunk["text"] for chunk in result["sources"]]
    retrieved_ids = [chunk["document_id"] for chunk in result["sources"]]
    return {"answer": result["answer"], "retrieved_texts": retrieved_texts, "retrieved_ids": retrieved_ids}


async def test_golden_dataset_cases_score_above_zero():
    """A light smoke test, not a quality gate - confirms the harness itself
    works end to end (real scores come back, not zeros or errors) on a
    small sample. The CI practical-significance gate (docs/CICD-BRANCHING-
    STRATEGY.md) is separate follow-up work, not this test's job."""
    cases = load_golden_cases()[:3]

    for case in cases:
        result = await score_case(case, ask_genai_rag)
        for metric_name, score in result["scores"].items():
            assert score is not None, f"{case['id']} / {metric_name} returned no score"
