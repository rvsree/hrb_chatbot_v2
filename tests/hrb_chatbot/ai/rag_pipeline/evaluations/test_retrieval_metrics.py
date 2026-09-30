"""Tests for Phase 62's deterministic retrieval metrics and failure-pattern
diagnostics - both pure functions ported from modules/5_evaluation/demo.py,
no real LLM call needed."""

from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import (
    calculate_retrieval_metrics,
    diagnose_failure_patterns,
)


def test_all_retrieved_docs_relevant_is_perfect_precision():
    metrics = calculate_retrieval_metrics(["a", "b", "c"], ["a", "b", "c"], k=3)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_no_overlap_is_zero_on_everything():
    metrics = calculate_retrieval_metrics(["x", "y", "z"], ["a", "b"], k=3)
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_partial_overlap_computes_precision_and_recall_independently():
    # 1 of top-3 retrieved is relevant; 1 of 2 total relevant docs was found.
    metrics = calculate_retrieval_metrics(["a", "x", "y"], ["a", "b"], k=3)
    assert metrics["precision"] == 1 / 3
    assert metrics["recall"] == 0.5
    assert metrics["true_positives"] == 1


def test_only_top_k_counts_not_the_full_retrieved_list():
    # "a" is relevant but retrieved 4th, outside k=3 - must not count.
    metrics = calculate_retrieval_metrics(["x", "y", "z", "a"], ["a"], k=3)
    assert metrics["true_positives"] == 0
    assert metrics["recall"] == 0.0


def test_empty_relevant_set_does_not_divide_by_zero():
    metrics = calculate_retrieval_metrics(["a", "b"], [], k=2)
    assert metrics["recall"] == 0.0
    assert metrics["relevant_count"] == 0


def test_pattern_a_high_precision_low_recall():
    patterns = diagnose_failure_patterns({"precision": 0.80, "recall": 0.50, "groundedness": 0.90, "completeness": 0.90})
    assert any("PATTERN A" in pattern for pattern in patterns)


def test_pattern_b_low_precision_high_recall():
    patterns = diagnose_failure_patterns({"precision": 0.50, "recall": 0.80, "groundedness": 0.90, "completeness": 0.90})
    assert any("PATTERN B" in pattern for pattern in patterns)


def test_pattern_c_strong_retrieval_weak_generation():
    patterns = diagnose_failure_patterns(
        {"precision": 0.90, "recall": 0.85, "f1": 0.87, "groundedness": 0.60, "completeness": 0.90}
    )
    assert any("PATTERN C" in pattern for pattern in patterns)


def test_pattern_d_low_groundedness():
    patterns = diagnose_failure_patterns({"precision": 0.90, "recall": 0.85, "groundedness": 0.50, "completeness": 0.90})
    assert any("PATTERN D" in pattern for pattern in patterns)


def test_healthy_scores_trigger_no_patterns():
    patterns = diagnose_failure_patterns(
        {"precision": 0.85, "recall": 0.80, "f1": 0.82, "groundedness": 0.90, "completeness": 0.85}
    )
    assert patterns == []
