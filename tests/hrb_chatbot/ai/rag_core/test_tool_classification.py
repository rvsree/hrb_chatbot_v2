"""Phase 126 - classify_tool() is a pure function, tested exhaustively over the mapping + the fallback."""

import pytest

from src.hrb_chatbot.ai.rag_core.tool_classification import classify_tool

MAPPED_NAMES = [
    ("SearchKnowledgeBase", "vector_db"),
    ("vector_kb_agent", "vector_db"),
    ("GetLeaveBalance", "mcp"),
    ("GetLeaveHistory", "mcp"),
    ("get_leave_balance", "mcp"),
    ("get_leave_history", "mcp"),
    ("lms_ops_agent", "mcp"),
    ("web_search_agent", "web_search"),
    ("sql_db_agent", "sql_db"),
    ("lms_analytics_agent", "sql_db"),
]


@pytest.mark.parametrize("tool_name,expected_type", MAPPED_NAMES)
def test_classifies_every_known_tool_name(tool_name, expected_type):
    assert classify_tool(tool_name) == expected_type


def test_unknown_tool_name_falls_back_to_other():
    assert classify_tool("SomeFutureTool") == "other"
