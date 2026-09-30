"""Compares named retrieval configurations against the golden dataset - ported directly
from the IK FDE cohort's modules/5_evaluation/demo.py compare_configurations() (Phase 62).
Reuses calculate_retrieval_metrics() so a config comparison is scored identically to a
release-gate run, not a separate metric."""

from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import calculate_retrieval_metrics


async def compare_configurations(cases: list[dict], configs: dict, ask_factory) -> dict:
    """`configs` maps a config name to whatever `ask_factory(config_name)` needs to build an
    `ask(query) -> {"retrieved_ids": list[str]}` callable for that configuration - e.g.
    {"k=3": {"top_k": 3}, "k=5": {"top_k": 5}}. Only cases with a known relevant document
    (expected_source_document is not None) are scored, matching score_case()'s own rule."""
    scorable_cases = [case for case in cases if case.get("expected_source_document")]

    results = {}
    for config_name in configs:
        ask = ask_factory(config_name)

        precisions, recalls, f1s = [], [], []
        for case in scorable_cases:
            result = await ask(case["query"])
            retrieved_ids = result["retrieved_ids"]
            relevant_ids = [case["expected_source_document"]]

            metrics = calculate_retrieval_metrics(retrieved_ids, relevant_ids)
            precisions.append(metrics["precision"])
            recalls.append(metrics["recall"])
            f1s.append(metrics["f1"])

        results[config_name] = {
            "precision": sum(precisions) / len(precisions) if precisions else 0.0,
            "recall": sum(recalls) / len(recalls) if recalls else 0.0,
            "f1": sum(f1s) / len(f1s) if f1s else 0.0,
            "case_count": len(scorable_cases),
        }

    return results
