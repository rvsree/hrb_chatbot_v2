"""Runs all 14 NFR cases (Phase 51) against the real check_input() guardrail -
real LLM calls, real cost, excluded from the default suite, run with
`pytest -m eval -v`. Not mocked on purpose: this is the one place this
project checks real guardrail behavior against adversarial/false-positive
cases, for real."""

import pytest

from src.hrb_chatbot.ai.rag_pipeline.evaluations.nfr_golden_dataset_harness import load_nfr_cases, score_nfr_case

pytestmark = pytest.mark.eval


async def test_all_nfr_cases_match_expected_outcome():
    cases = load_nfr_cases()
    known_issue_ids = {case["id"] for case in cases if "known_issue" in case}
    results = [await score_nfr_case(case) for case in cases]

    new_failures = [r for r in results if not r["passed"] and r["case_id"] not in known_issue_ids]
    known_failures = [r for r in results if not r["passed"] and r["case_id"] in known_issue_ids]

    if known_failures:
        print(f"\n{len(known_failures)} known, already-documented failure(s) (see nfr_golden_dataset.json): {known_failures}")

    assert not new_failures, f"{len(new_failures)}/{len(cases)} NFR case(s) failed with NO known_issue on record: {new_failures}"
