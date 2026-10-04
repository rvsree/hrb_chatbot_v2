"""LMS Analytics Agent is an honest stub - no historical dataset exists yet, confirms it says so plainly."""

from src.hrb_chatbot.ai.agents.domain_agents import lms_analytics_agent


async def test_run_reports_not_available():
    result = await lms_analytics_agent.run("some historical analytics question")

    assert result == lms_analytics_agent.NOT_AVAILABLE_MESSAGE
