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


class _CapturingLlm:
    def __init__(self, response, captured_calls):
        self._response = response
        self._captured_calls = captured_calls

    async def ainvoke(self, messages):
        self._captured_calls.append(messages)
        return self._response


async def test_tabular_instruction_added_when_query_says_summarize(monkeypatch):
    captured_calls = []
    monkeypatch.setattr(
        reviewer_agent, "_build_llm", lambda: _CapturingLlm(FakeResponse("| a | b |"), captured_calls)
    )

    await reviewer_agent.review(
        "summarize my benefits",
        [
            {"agent": "vector_kb_agent", "focus": "benefits", "result": "8 weeks paid."},
            {"agent": "lms_ops_agent", "focus": "balance", "result": "10 days available."},
        ],
    )

    system_message = captured_calls[0][0]
    assert "markdown table" in system_message.content


async def test_tabular_instruction_absent_for_a_plain_query(monkeypatch):
    captured_calls = []
    monkeypatch.setattr(
        reviewer_agent, "_build_llm", lambda: _CapturingLlm(FakeResponse("8 weeks paid, 10 days available."), captured_calls)
    )

    await reviewer_agent.review(
        "what is the leave policy and my balance?",
        [
            {"agent": "vector_kb_agent", "focus": "benefits", "result": "8 weeks paid."},
            {"agent": "lms_ops_agent", "focus": "balance", "result": "10 days available."},
        ],
    )

    system_message = captured_calls[0][0]
    assert "markdown table" not in system_message.content


async def test_generate_follow_ups_parses_one_question_per_line(monkeypatch):
    _patch_llm(monkeypatch, "What is my dental plan?\nHow do I enroll in a 401(k)?\n")

    follow_ups = await reviewer_agent.generate_follow_ups("What is my PTO balance?", "You have 10 days left.")

    assert follow_ups == ["What is my dental plan?", "How do I enroll in a 401(k)?"]


async def test_generate_follow_ups_returns_empty_list_on_llm_failure(monkeypatch):
    class _FailingLlm:
        async def ainvoke(self, messages):
            raise RuntimeError("LLM is down")

    monkeypatch.setattr(reviewer_agent, "_build_llm", lambda: _FailingLlm())

    follow_ups = await reviewer_agent.generate_follow_ups("What is my PTO balance?", "You have 10 days left.")

    assert follow_ups == []
