"""Tests for the Phase 49 MCP routing prototype (ai/rag_pipeline/tools/
mcp_tools/__init__.py). get_leave_balance/get_leave_history are faked here -
no real network call to hrb_lms_mcp, matching every other client test in
this project."""

from src.hrb_chatbot.ai.rag_pipeline.tools import mcp_tools


def test_leave_balance_keywords_match():
    assert mcp_tools.is_leave_balance_query("What's my PTO balance?")
    assert mcp_tools.is_leave_balance_query("How many days off do I have left")
    assert not mcp_tools.is_leave_balance_query("How does 401k vesting work?")


def test_leave_history_keywords_match():
    assert mcp_tools.is_leave_history_query("Show me my leave history")
    assert not mcp_tools.is_leave_history_query("What's my PTO balance?")


async def test_matched_query_with_employee_id_routes_to_mcp(monkeypatch):
    async def _fake_get_leave_balance(employee_id):
        return {"tool": "get_leave_balance", "content": [f"balance for {employee_id}"]}

    monkeypatch.setattr(mcp_tools, "get_leave_balance", _fake_get_leave_balance)

    result = await mcp_tools.try_route_to_mcp("What's my PTO balance?", "EMP052")

    assert result is not None
    assert result["routed_to"] == "get_leave_balance"
    assert result["answer"] == "balance for EMP052"
    assert result["sources"] == []


async def test_unmatched_query_falls_through_to_none():
    result = await mcp_tools.try_route_to_mcp("How does 401k vesting work?", "EMP052")
    assert result is None


async def test_matched_query_without_employee_id_falls_through_to_none():
    result = await mcp_tools.try_route_to_mcp("What's my PTO balance?", None)
    assert result is None


async def test_mcp_failure_falls_through_to_none_not_raise(monkeypatch):
    async def _fake_get_leave_balance_raising(employee_id):
        raise ConnectionError("hrb_lms_mcp unreachable")

    monkeypatch.setattr(mcp_tools, "get_leave_balance", _fake_get_leave_balance_raising)

    result = await mcp_tools.try_route_to_mcp("What's my PTO balance?", "EMP052")

    assert result is None
