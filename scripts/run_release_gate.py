#!/usr/bin/env python
"""Release gate (Phase 80) - runs every scorable golden-dataset case
through genai-rag's real pipeline.answer_query(), aggregates scores, and
calls the existing get_release_decision() to produce a PASS/REVIEW/BLOCK
verdict. Exits non-zero on BLOCK, so CI fails the job. Real LLM calls,
real cost - meant to be triggered by hand (or the eval-gate.yml workflow's
own manual trigger), not run automatically."""

import asyncio
import json
import sys

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import (
    GOLDEN_DATASET_PATH,
    calculate_retrieval_metrics,
    evaluate_completeness,
    evaluate_groundedness,
    get_release_decision,
)
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

METRICS = ("precision", "recall", "f1", "groundedness", "completeness")

# calculate_retrieval_metrics() defaults to k=3 (the IK FDE course's own
# demo.py value) - genai-rag actually retrieves RAG_DEFAULT_TOP_K chunks
# (5 by default). Passing the real k here (instead of score_case()'s own
# hardcoded k=3) is still correct - it reflects this project's real
# retrieval depth - but confirmed live it does NOT remove the structural
# ceiling: every golden case has exactly 1 relevant document, and
# precision@k = (relevant found)/k can never exceed 1/k when only 1
# relevant document can ever exist - 0.2 at k=5, worse than k=3's 0.33, not
# better. This is a mismatch between the metric (built for narrow
# search-result ranking, assuming several relevant results could appear)
# and this project's actual design (deliberately broad multi-chunk RAG
# context, one labeled canonical source per case) - not a quality problem,
# confirmed by recall sitting at 1.0 on nearly every case (the right
# document is always found). GATE_METRICS below is what actually feeds
# get_release_decision() - precision/f1 are still computed and printed per
# case as informational context, just never block a release.
RETRIEVAL_K = int(read_setting(None, "RAG_DEFAULT_TOP_K", 5))
GATE_METRICS = ("recall", "groundedness", "completeness")


def _load_scorable_cases() -> list[dict]:
    """Golden cases, with expected_source_document resolved from the dataset's
    own short keys ("401k.pdf") to the real uploaded filename chunks actually
    carry ("JPMC Empower 401(k) Savings Plan.pdf") - confirmed live, before this
    fix, every case's precision/recall/f1 came back 0.0 because nothing was ever
    comparing against the right value, which would have made this gate always
    report BLOCK regardless of real retrieval quality. agent_call cases
    (Phase 73) are excluded - they bypass retrieval/generation entirely via
    genai-rag's own MCP routing, so scoring them against these metrics isn't meaningful."""
    with open(GOLDEN_DATASET_PATH, encoding="utf-8") as file:
        data = json.load(file)

    source_documents = data["_meta"]["source_documents"]
    cases = []
    for case in data["cases"]:
        if case.get("call_type") == "agent_call":
            continue
        resolved_case = dict(case)
        short_key = case.get("expected_source_document")
        if short_key:
            resolved_case["expected_source_document"] = source_documents.get(short_key, short_key)
        cases.append(resolved_case)
    return cases


async def ask_genai_rag(query: str) -> dict:
    """Same adapter shape test_golden_dataset_harness.py already established,
    with retrieved_ids corrected to the real filename (not document_id, a UUID
    that can never match expected_source_document regardless of retrieval quality)."""
    result = await pipeline.answer_query(RagQueryParams(query=query))
    retrieved_texts = [chunk["text"] for chunk in result["sources"]]
    retrieved_ids = [chunk["filename"] for chunk in result["sources"]]
    return {"answer": result["answer"], "retrieved_texts": retrieved_texts, "retrieved_ids": retrieved_ids}


async def score_case_with_real_k(case: dict) -> dict:
    """Same shape/logic as golden_dataset_harness.py's own score_case(), just
    with calculate_retrieval_metrics() given the real retrieval depth
    (RETRIEVAL_K) instead of that function's own hardcoded k=3 default."""
    result = await ask_genai_rag(case["query"])
    answer = result["answer"]
    retrieved_texts = result["retrieved_texts"]
    retrieved_ids = result["retrieved_ids"]

    expected_source = case.get("expected_source_document")
    relevant_ids = [expected_source] if expected_source else []

    scores = {}
    if relevant_ids:
        retrieval_scores = calculate_retrieval_metrics(retrieved_ids, relevant_ids, k=RETRIEVAL_K)
        scores["precision"] = retrieval_scores["precision"]
        scores["recall"] = retrieval_scores["recall"]
        scores["f1"] = retrieval_scores["f1"]

    groundedness = evaluate_groundedness(answer, retrieved_texts)
    completeness = evaluate_completeness(case["query"], answer, case.get("expected_answer"))
    scores["groundedness"] = groundedness["score"]
    scores["completeness"] = completeness["score"]

    return {"case_id": case["id"], "category": case["category"], "scores": scores}


async def main() -> int:
    scorable_cases = _load_scorable_cases()

    per_metric_scores: dict[str, list[float]] = {metric: [] for metric in METRICS}
    print(f"Scoring {len(scorable_cases)} golden case(s) against genai-rag (retrieval k={RETRIEVAL_K})...\n")

    for case in scorable_cases:
        result = await score_case_with_real_k(case)
        for metric, score in result["scores"].items():
            if metric in per_metric_scores and score is not None:
                per_metric_scores[metric].append(score)
        print(f"  {case['id']}: {result['scores']}")

    aggregated = {metric: sum(scores) / len(scores) for metric, scores in per_metric_scores.items() if scores}

    print("\nAggregated scores (averaged across all scored cases):")
    for metric, value in aggregated.items():
        gated = " (gates the verdict)" if metric in GATE_METRICS else " (informational only - see script docstring)"
        print(f"  {metric}: {value:.3f}{gated}")

    gate_scores = {metric: value for metric, value in aggregated.items() if metric in GATE_METRICS}
    decision, flags = get_release_decision(gate_scores)
    print(f"\nRelease decision: {decision}")
    for flag in flags:
        print(f"  - {flag}")

    return 1 if decision == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
