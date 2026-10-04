"""SQL DB Agent is an honest stub - no database exists yet, confirms it says so plainly."""

from src.hrb_chatbot.ai.agents.domain_agents import sql_db_agent


async def test_run_reports_not_available():
    result = await sql_db_agent.run("some structured HR data question")

    assert result == sql_db_agent.NOT_AVAILABLE_MESSAGE
