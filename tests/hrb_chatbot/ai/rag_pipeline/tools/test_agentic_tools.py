"""Tests for Phase 55's 3 agent tools - retrieve_chunks/get_leave_balance/
get_leave_history are all faked, no real network call, matching every
other client test in this project."""

from src.hrb_chatbot.ai.rag_pipeline.tools import agentic_tools


async def test_search_knowledge_base_formats_chunks(monkeypatch):
    async def _fake_retrieve_chunks(query, top_k=5, **kwargs):
        return ([{"filename": "401k.pdf", "text": "Match is 100% up to 5%."}], None)

    monkeypatch.setattr(agentic_tools, "retrieve_chunks", _fake_retrieve_chunks)

    result = await agentic_tools.search_knowledge_base("What's the 401k match?")

    assert "401k.pdf" in result
    assert "Match is 100% up to 5%." in result


async def test_search_knowledge_base_empty_query_is_an_error_string_not_a_crash():
    result = await agentic_tools.search_knowledge_base("")
    assert result.startswith("Error:")


async def test_search_knowledge_base_defaults_to_similarity(monkeypatch):
    captured = {}

    async def _fake_retrieve_chunks(query, top_k=5, search_strategy=None, **kwargs):
        captured["search_strategy"] = search_strategy
        return ([{"filename": "x.pdf", "text": "y"}], None)

    monkeypatch.setattr(agentic_tools, "retrieve_chunks", _fake_retrieve_chunks)

    await agentic_tools.search_knowledge_base("narrow question")

    assert captured["search_strategy"] == "similarity"


async def test_search_knowledge_base_passes_through_mmr_when_the_agent_asks_for_it(monkeypatch):
    captured = {}

    async def _fake_retrieve_chunks(query, top_k=5, search_strategy=None, **kwargs):
        captured["search_strategy"] = search_strategy
        return ([{"filename": "x.pdf", "text": "y"}], None)

    monkeypatch.setattr(agentic_tools, "retrieve_chunks", _fake_retrieve_chunks)

    await agentic_tools.search_knowledge_base("broad question", search_strategy="mmr")

    assert captured["search_strategy"] == "mmr"


async def test_search_knowledge_base_invalid_strategy_falls_back_to_similarity_not_a_crash(monkeypatch):
    captured = {}

    async def _fake_retrieve_chunks(query, top_k=5, search_strategy=None, **kwargs):
        captured["search_strategy"] = search_strategy
        return ([], None)

    monkeypatch.setattr(agentic_tools, "retrieve_chunks", _fake_retrieve_chunks)

    await agentic_tools.search_knowledge_base("question", search_strategy="not-a-real-strategy")

    assert captured["search_strategy"] == "similarity"


async def test_search_knowledge_base_no_results(monkeypatch):
    async def _fake_retrieve_chunks(query, top_k=5, **kwargs):
        return ([], None)

    monkeypatch.setattr(agentic_tools, "retrieve_chunks", _fake_retrieve_chunks)

    result = await agentic_tools.search_knowledge_base("obscure question")

    assert "No relevant" in result


async def test_get_leave_balance_tool_formats_mcp_content(monkeypatch):
    async def _fake_get_leave_balance(employee_id):
        return {"tool": "get_leave_balance", "content": ['{"available": 11.0}']}

    monkeypatch.setattr(agentic_tools, "get_leave_balance", _fake_get_leave_balance)

    result = await agentic_tools.get_leave_balance_tool("EMP052")

    assert "available" in result


async def test_get_leave_balance_tool_missing_employee_id_is_an_error_string():
    result = await agentic_tools.get_leave_balance_tool("")
    assert result.startswith("Error:")


async def test_get_leave_history_tool_wraps_failure_as_error_string_not_crash(monkeypatch):
    async def _fake_get_leave_history_raising(employee_id):
        raise ConnectionError("hrb_lms_mcp unreachable")

    monkeypatch.setattr(agentic_tools, "get_leave_history", _fake_get_leave_history_raising)

    result = await agentic_tools.get_leave_history_tool("EMP052")

    assert result.startswith("Error:")
