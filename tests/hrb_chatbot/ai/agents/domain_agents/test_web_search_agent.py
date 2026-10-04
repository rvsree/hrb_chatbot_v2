"""Web Search Agent (Phase 70) is a thin wrapper over the existing Tavily
client - confirms the success, empty, and error-string shapes, never raises."""

from src.hrb_chatbot.ai.agents.domain_agents import web_search_agent


class FakeTavilyClient:
    def __init__(self, result):
        self._result = result

    def search(self, query, max_results=5, search_depth="basic", include_answer=True, max_retries=3):
        return self._result


def _patch_tavily(monkeypatch, result):
    fake_gateway = type("FakeGateway", (), {"tavily": lambda self: FakeTavilyClient(result)})()
    monkeypatch.setattr(web_search_agent, "get_client_gateway", lambda: fake_gateway)


async def test_successful_search_includes_answer_and_sources(monkeypatch):
    _patch_tavily(
        monkeypatch,
        {
            "results": [{"title": "IRS mileage rate 2026", "content": "67 cents per mile.", "url": "https://irs.gov/x"}],
            "answer": "The 2026 federal mileage rate is 67 cents per mile.",
            "query": "federal mileage reimbursement rate",
        },
    )

    result = await web_search_agent.run("federal mileage reimbursement rate")

    assert "67 cents per mile" in result
    assert "IRS mileage rate 2026" in result
    assert "https://irs.gov/x" in result


async def test_no_results_returns_a_clear_message(monkeypatch):
    _patch_tavily(monkeypatch, {"results": [], "answer": "", "query": "some obscure query"})

    result = await web_search_agent.run("some obscure query")

    assert result == "No relevant web search results found."


async def test_client_error_becomes_an_error_string_not_a_crash(monkeypatch):
    _patch_tavily(
        monkeypatch,
        {"results": [], "answer": "", "query": "x", "error": "TAVILY_API_KEY not configured"},
    )

    result = await web_search_agent.run("x")

    assert result == "Error: web search failed (TAVILY_API_KEY not configured)."
