"""Scores Gate 1 (input guardrail) behavior - separate from golden_dataset_harness.py, which scores answer quality."""

import json

from src.hrb_chatbot.ai.pre_processing.guardrails_input import GuardrailBlockedError, check_input

NFR_GOLDEN_DATASET_PATH = "resources/golden_dataset/nfr_golden_dataset.json"


def load_nfr_cases() -> list[dict]:
    with open(NFR_GOLDEN_DATASET_PATH, encoding="utf-8") as file:
        data = json.load(file)
    return data["cases"]


async def score_nfr_case(case: dict) -> dict:
    """'blocked' if check_input() raises, 'masked' if the query changed, else 'pass'."""
    try:
        checked_query = await check_input(case["query"])
        actual_outcome = "pass" if checked_query == case["query"] else "masked"
    except GuardrailBlockedError:
        actual_outcome = "blocked"

    return {
        "case_id": case["id"],
        "category": case["category"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": actual_outcome,
        "passed": actual_outcome == case["expected_outcome"],
    }
