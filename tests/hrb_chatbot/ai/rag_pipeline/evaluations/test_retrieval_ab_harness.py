"""Tests for Phase 62's A/B config-comparison harness, ported from
modules/5_evaluation/demo.py's compare_configurations(). Uses a fake
ask_factory - no real LLM/retrieval call, no eval marker needed."""

from src.hrb_chatbot.ai.rag_pipeline.evaluations.retrieval_ab_harness import compare_configurations

CASES = [
    {"id": "c1", "query": "q1", "expected_source_document": "policy_a.pdf"},
    {"id": "c2", "query": "q2", "expected_source_document": "policy_b.pdf"},
    {"id": "c3", "query": "q3", "expected_source_document": None},  # out of scope - must be excluded
]

# Fixed, config-specific retrieval results so the comparison is deterministic.
FAKE_RESULTS = {
    "k=1": {
        "q1": ["policy_a.pdf"],
        "q2": ["policy_x.pdf"],
    },
    "k=3": {
        "q1": ["policy_a.pdf", "policy_z.pdf", "policy_y.pdf"],
        "q2": ["policy_x.pdf", "policy_b.pdf", "policy_w.pdf"],
    },
}


def make_ask_factory(k: int):
    def ask_factory(config_name: str):
        async def ask(query: str) -> dict:
            return {"retrieved_ids": FAKE_RESULTS[config_name][query][:k]}

        return ask

    return ask_factory


async def test_out_of_scope_cases_are_excluded_from_scoring():
    results = await compare_configurations(CASES, {"k=1": None}, make_ask_factory(1))
    assert results["k=1"]["case_count"] == 2


async def test_larger_k_can_change_recall_for_the_same_config_family():
    # k=1: only q1 hits (top-1 for q2 is wrong doc) -> recall 0.5 across 2 cases.
    # k=3: q1 and q2 both contain the relevant doc within top-3 -> recall 1.0.
    results = await compare_configurations(CASES, {"k=1": None, "k=3": None}, lambda name: make_ask_factory(1 if name == "k=1" else 3)(name))
    assert results["k=1"]["recall"] == 0.5
    assert results["k=3"]["recall"] == 1.0


async def test_report_shape_has_one_entry_per_config():
    results = await compare_configurations(CASES, {"k=1": None, "k=3": None}, lambda name: make_ask_factory(1 if name == "k=1" else 3)(name))
    assert set(results.keys()) == {"k=1", "k=3"}
    for config_result in results.values():
        assert set(config_result.keys()) == {"precision", "recall", "f1", "case_count"}
