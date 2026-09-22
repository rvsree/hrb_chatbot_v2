"""Tests for check_output() (guardrails_output/__init__.py) - Gate 6.
get_rails() is faked, so no real LLM call and no API key needed."""

from src.hrb_chatbot.ai.rag_pipeline.response_generation import guardrails_output
from src.hrb_chatbot.ai.rag_pipeline.response_generation.guardrails_output import SAFE_FALLBACK_ANSWER, check_output


class FakeRailsResult:
    def __init__(self, status, content="", rail=None):
        self.status = status
        self.content = content
        self.rail = rail


class FakeRails:
    """Stands in for nemoguardrails.LLMRails - no real LLM call."""

    def __init__(self, status, content="", rail=None):
        self._result = FakeRailsResult(status, content, rail)

    async def check_async(self, messages, rail_types=None):
        return self._result


async def test_a_normal_answer_passes_through_unchanged(monkeypatch):
    answer = "You get 16 weeks of parental leave."
    monkeypatch.setattr(guardrails_output, "get_rails", lambda: FakeRails("passed", content=answer))

    result = await check_output("How much leave?", answer)

    assert result == answer


async def test_a_blocked_answer_returns_the_safe_fallback(monkeypatch):
    monkeypatch.setattr(guardrails_output, "get_rails", lambda: FakeRails("blocked", rail="self check output"))

    result = await check_output("test", "some unsafe answer")

    assert result == SAFE_FALLBACK_ANSWER


async def test_a_modified_answer_returns_the_masked_text(monkeypatch):
    monkeypatch.setattr(guardrails_output, "get_rails", lambda: FakeRails("modified", content="Contact <MASKED>"))

    result = await check_output("test", "Contact john@example.com")

    assert result == "Contact <MASKED>"
