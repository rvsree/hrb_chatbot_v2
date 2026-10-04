"""LMS Ops Agent routes by keyword to the right existing MCP-backed tool."""

from src.hrb_chatbot.ai.agents.domain_agents import lms_ops_agent


async def test_balance_question_calls_balance_tool(monkeypatch):
    async def _fake_balance(employee_id):
        return f"balance for {employee_id}"

    monkeypatch.setattr(lms_ops_agent, "get_leave_balance_tool", _fake_balance)

    result = await lms_ops_agent.run("what's my leave balance?", employee_id="EMP052")

    assert result == "balance for EMP052"


async def test_history_question_calls_history_tool(monkeypatch):
    async def _fake_history(employee_id):
        return f"history for {employee_id}"

    monkeypatch.setattr(lms_ops_agent, "get_leave_history_tool", _fake_history)

    result = await lms_ops_agent.run("show my leave history", employee_id="EMP052")

    assert result == "history for EMP052"


async def test_missing_employee_id_is_a_clear_error_not_a_crash():
    result = await lms_ops_agent.run("what's my leave balance?", employee_id=None)

    assert "Error" in result
