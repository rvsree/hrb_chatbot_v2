"""Scores retrieval + generation against the golden dataset (Phase 8).
Takes any pipeline as a plain function - not hardcoded to genai-rag, so
single/multi-agentic-rag can be graded later by passing a different one in."""

import json

# Import settings first so DEEPEVAL_TELEMETRY_OPT_OUT is set in os.environ
# before deepeval's own telemetry module checks it at import time.
from src.hrb_chatbot.common.config import settings  # noqa: F401

from deepeval.metrics import AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

GOLDEN_DATASET_PATH = "resources/golden_dataset/golden_dataset.json"
JUDGE_MODEL = "gpt-4.1-mini"


def load_golden_cases() -> list[dict]:
    with open(GOLDEN_DATASET_PATH, encoding="utf-8") as file:
        data = json.load(file)
    return data["cases"]


def build_metrics() -> dict:
    """One instance per call - DeepEval metrics carry per-run state."""
    return {
        "contextual_precision": ContextualPrecisionMetric(model=JUDGE_MODEL),
        "contextual_recall": ContextualRecallMetric(model=JUDGE_MODEL),
        "faithfulness": FaithfulnessMetric(model=JUDGE_MODEL),
        "answer_relevancy": AnswerRelevancyMetric(model=JUDGE_MODEL),
    }


async def score_case(case: dict, ask) -> dict:
    """Runs one golden-dataset case through `ask` and scores it.
    `ask(query)` must return {"answer": str, "retrieved_texts": list[str]}."""
    result = await ask(case["query"])

    test_case = LLMTestCase(
        input=case["query"],
        actual_output=result["answer"],
        expected_output=case["expected_answer"],
        retrieval_context=result["retrieved_texts"],
    )

    scores = {}
    for name, metric in build_metrics().items():
        metric.measure(test_case)
        scores[name] = metric.score

    return {"case_id": case["id"], "category": case["category"], "scores": scores}
