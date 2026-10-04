"""Reviewer Agent tests - 0/1/2+ branching. The 2+ case fakes the LLM; 0/1 never call it."""

from src.hrb_chatbot.ai.agents.workflow_agents import reviewer_agent


class FakeResponse:
    def __init__(self, content):
        self.content = content
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


class FakeLlm:
    def __init__(self, response):
        self._response = response

    async def ainvoke(self, messages):
        return self._response


def _patch_llm(monkeypatch, content):
    monkeypatch.setattr(reviewer_agent, "_build_llm", lambda: FakeLlm(FakeResponse(content)))


async def test_zero_results_gives_a_clear_fallback():
    answer = await reviewer_agent.review("what is the policy?", [])

    assert "wasn't able to find" in answer


async def test_one_result_is_returned_as_is_no_llm_call(monkeypatch):
    def _fail_if_called():
        raise AssertionError("LLM should not be called for a single result")

    monkeypatch.setattr(reviewer_agent, "_build_llm", _fail_if_called)

    answer = await reviewer_agent.review(
        "what is the parental leave policy?",
        [{"agent": "vector_kb_agent", "focus": "parental leave policy", "result": "8 weeks paid."}],
    )

    assert answer == "8 weeks paid."


async def test_two_or_more_results_are_merged_by_the_llm(monkeypatch):
    _patch_llm(monkeypatch, "Parental leave is 8 weeks paid. Your current balance is 10 days.")

    answer = await reviewer_agent.review(
        "what is the parental leave policy and what's my leave balance?",
        [
            {"agent": "vector_kb_agent", "focus": "parental leave policy", "result": "8 weeks paid."},
            {"agent": "lms_ops_agent", "focus": "my leave balance", "result": "10 days available."},
        ],
    )

    assert answer == "Parental leave is 8 weeks paid. Your current balance is 10 days."
