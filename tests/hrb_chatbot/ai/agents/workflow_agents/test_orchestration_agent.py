"""Tests for Phase 55's tool-calling loop - the LLM itself is faked (no
real API call), matching every other client test in this project. Each
fake mirrors just enough of ChatOpenAI's shape (.bind().ainvoke()) to
drive the loop's branching."""

from src.hrb_chatbot.ai.agents.workflow_agents import orchestration_agent
from src.hrb_chatbot.ai.pre_processing import conversation_memory


class FakeResponse:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeBoundLlm:
    def __init__(self, responses):
        self._responses = list(responses)

    async def ainvoke(self, messages):
        return self._responses.pop(0)


class FakeLlm:
    def __init__(self, responses):
        self._responses = responses

    def bind(self, tools):
        return FakeBoundLlm(self._responses)


def _patch_llm(monkeypatch, responses):
    monkeypatch.setattr(orchestration_agent, "_build_llm", lambda: FakeLlm(responses))


async def test_no_tool_call_needed_answers_in_one_iteration(monkeypatch):
    _patch_llm(monkeypatch, [FakeResponse(content="Hello, how can I help?")])

    result = await orchestration_agent.run_agent("hi", employee_id="EMP052")

    assert result["answer"] == "Hello, how can I help?"
    assert result["tools_used"] == []
    assert result["iterations"] == 1


async def test_one_tool_call_then_final_answer(monkeypatch):
    async def _fake_search(args):
        return "fake KB result"

    monkeypatch.setattr(
        orchestration_agent,
        "TOOL_FUNCTIONS",
        {"SearchKnowledgeBase": lambda args, employee_id: _fake_search(args)},
    )
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(tool_calls=[{"name": "SearchKnowledgeBase", "args": {"input": "401k match?"}, "id": "call_1"}]),
            FakeResponse(content="The match is 100% up to 5%."),
        ],
    )

    result = await orchestration_agent.run_agent("What's the 401k match?", employee_id="EMP052")

    assert result["answer"] == "The match is 100% up to 5%."
    assert result["tools_used"] == [{"tool_name": "SearchKnowledgeBase", "tool_input": "401k match?"}]
    assert result["iterations"] == 2


async def test_search_strategy_arg_is_forwarded_to_the_real_tool_function(monkeypatch):
    captured = {}

    async def _fake_search_knowledge_base(query, search_strategy=None):
        captured["query"] = query
        captured["search_strategy"] = search_strategy
        return "fake result"

    monkeypatch.setattr(orchestration_agent, "search_knowledge_base", _fake_search_knowledge_base)
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(
                tool_calls=[
                    {
                        "name": "SearchKnowledgeBase",
                        "args": {"input": "what benefits programs exist", "search_strategy": "mmr"},
                        "id": "call_1",
                    }
                ]
            ),
            FakeResponse(content="Here's an overview."),
        ],
    )

    await orchestration_agent.run_agent("what benefits programs exist", employee_id="EMP052")

    assert captured["query"] == "what benefits programs exist"
    assert captured["search_strategy"] == "mmr"


async def test_max_iterations_reached_gives_a_clear_fallback_not_a_crash(monkeypatch):
    always_calls_tool = FakeResponse(tool_calls=[{"name": "SearchKnowledgeBase", "args": {"input": "x"}, "id": "call_1"}])
    monkeypatch.setattr(
        orchestration_agent, "TOOL_FUNCTIONS", {"SearchKnowledgeBase": lambda args, employee_id: _noop()}
    )
    _patch_llm(monkeypatch, [always_calls_tool] * 3)

    result = await orchestration_agent.run_agent("loop forever", employee_id="EMP052", max_iterations=3)

    assert "wasn't able to finish" in result["answer"]
    assert result["iterations"] == 3


async def _noop():
    return "tool output"


async def test_conversation_memory_disabled_by_default_no_conversation_id_returned(monkeypatch):
    _patch_llm(monkeypatch, [FakeResponse(content="Hello, how can I help?")])

    result = await orchestration_agent.run_agent("hi", employee_id="EMP052")

    assert result["conversation_id"] is None


async def test_enabling_memory_without_an_id_generates_one_and_saves_the_turn(monkeypatch):
    conversation_memory._CONVERSATIONS.clear()
    _patch_llm(monkeypatch, [FakeResponse(content="The match is 100% up to 5%.")])

    result = await orchestration_agent.run_agent(
        "What's the 401k match?", employee_id="EMP052", enable_conversation_memory=True
    )

    assert result["conversation_id"] is not None
    saved = conversation_memory.load_history(result["conversation_id"])
    assert [m.content for m in saved] == ["What's the 401k match?", "The match is 100% up to 5%."]


async def test_an_existing_conversation_id_seeds_prior_history_into_the_messages(monkeypatch):
    conversation_memory._CONVERSATIONS.clear()
    conversation_memory.save_turn("conv-1", "what database issues have we had?", "Two timeout tickets.")

    captured_messages = {}

    class CapturingFakeLlm(FakeLlm):
        def bind(self, tools):
            bound = super().bind(tools)
            original_ainvoke = bound.ainvoke

            async def ainvoke(messages):
                captured_messages["messages"] = list(messages)
                return await original_ainvoke(messages)

            bound.ainvoke = ainvoke
            return bound

    monkeypatch.setattr(
        orchestration_agent, "_build_llm", lambda: CapturingFakeLlm([FakeResponse(content="It was TICK-042.")])
    )

    result = await orchestration_agent.run_agent(
        "what was the ticket ID for that?",
        employee_id="EMP052",
        enable_conversation_memory=True,
        conversation_id="conv-1",
    )

    assert result["conversation_id"] == "conv-1"
    contents = [m.content for m in captured_messages["messages"]]
    assert contents == [
        orchestration_agent.SYSTEM_PROMPT,
        "what database issues have we had?",
        "Two timeout tickets.",
        "what was the ticket ID for that?",
    ]
