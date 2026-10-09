"""Phase 122 - should_use_tabular_format() is a pure function, tested exhaustively."""

import pytest

from src.hrb_chatbot.ai.rag_core.response_format import should_use_tabular_format

TRIGGERING_QUERIES = [
    "Summarize my benefits",
    "Can you give me a summary of my PTO?",
    "Show this in a table",
    "Give me the table format",
    "Put this in a tabular view",
    "SUMMARIZE this for me",
]

NON_TRIGGERING_QUERIES = [
    "What is my dental plan?",
    "How many PTO days do I have left?",
    "",
]


@pytest.mark.parametrize("query", TRIGGERING_QUERIES)
def test_triggers_on_summarize_signal_keywords(query):
    assert should_use_tabular_format(query) is True


@pytest.mark.parametrize("query", NON_TRIGGERING_QUERIES)
def test_does_not_trigger_on_plain_queries(query):
    assert should_use_tabular_format(query) is False
