"""Tests for Phase 62's release-gate decision logic (course's own metric
naming: precision/recall/f1/groundedness/completeness) - pure function,
no real LLM call needed."""

from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import get_release_decision


def test_all_metrics_above_pass_threshold_is_pass():
    decision, flags = get_release_decision(
        {"precision": 0.90, "recall": 0.85, "groundedness": 0.95, "completeness": 0.90}
    )
    assert decision == "PASS"
    assert flags == []


def test_one_metric_between_review_and_pass_is_review():
    decision, flags = get_release_decision(
        {"precision": 0.75, "recall": 0.85, "groundedness": 0.95, "completeness": 0.90}
    )
    assert decision == "REVIEW"
    assert any("precision" in flag for flag in flags)


def test_one_metric_below_review_threshold_is_block():
    decision, flags = get_release_decision(
        {"precision": 0.90, "recall": 0.85, "groundedness": 0.50, "completeness": 0.90}
    )
    assert decision == "BLOCK"
    assert any("groundedness" in flag for flag in flags)


def test_f1_is_computed_from_precision_and_recall_not_passed_in():
    # precision=0.72 (>=0.70 review, <0.80 pass -> yellow), recall=0.68 (>=0.60 review, <0.70 pass -> yellow)
    # f1 = 2*0.72*0.68/(0.72+0.68) = 0.6994 (>=0.65 review, <0.75 pass -> yellow)
    # No metric here trips a BLOCK, so f1's own yellow flag must show up in the REVIEW result -
    # proving f1 was actually computed, not just missing/defaulted to 0.
    decision, flags = get_release_decision(
        {"precision": 0.72, "recall": 0.68, "groundedness": 0.95, "completeness": 0.90}
    )
    assert decision == "REVIEW"
    assert any("f1" in flag for flag in flags)


def test_block_wins_over_review_when_both_present():
    decision, flags = get_release_decision(
        {"precision": 0.75, "recall": 0.30, "groundedness": 0.95, "completeness": 0.90}
    )
    assert decision == "BLOCK"


def test_f1_passed_in_directly_is_not_recomputed():
    # Passing f1 explicitly (as the A/B harness does) must use that value, not
    # silently recompute it from precision/recall.
    decision, flags = get_release_decision(
        {"precision": 0.90, "recall": 0.90, "f1": 0.50, "groundedness": 0.95, "completeness": 0.90}
    )
    assert decision == "BLOCK"
    assert any("f1" in flag for flag in flags)
