"""Contract/schema regression testing (Phase 74) - locks each of the 3 query-
response models' JSON schema to a committed file in contract_snapshots/, so
a field silently renamed/retyped/removed fails here instead of only
reaching a client. No new library - plain Pydantic model_json_schema() +
a committed JSON file. A deliberate contract change updates the committed
file in the same PR, not silently."""

import json
from pathlib import Path

import pytest

from src.hrb_chatbot.models.agentic_rag import AgenticRagResponse
from src.hrb_chatbot.models.multi_agentic_rag import MultiAgenticRagResponse
from src.hrb_chatbot.models.rag import RagQueryResponse

SNAPSHOT_DIR = Path(__file__).parent / "contract_snapshots"

LOCKED_MODELS = {
    "RagQueryResponse": RagQueryResponse,
    "AgenticRagResponse": AgenticRagResponse,
    "MultiAgenticRagResponse": MultiAgenticRagResponse,
}


@pytest.mark.parametrize("name,model", LOCKED_MODELS.items())
def test_schema_matches_committed_snapshot(name, model):
    snapshot_path = SNAPSHOT_DIR / f"{name}.json"
    if not snapshot_path.exists():
        pytest.fail(f"No snapshot committed for {name} at {snapshot_path} - generate one first.")

    expected_schema = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual_schema = model.model_json_schema()

    assert actual_schema == expected_schema, (
        f"{name}'s response schema changed. If this is a deliberate contract change, "
        f"regenerate {snapshot_path} - don't just make this test pass."
    )
