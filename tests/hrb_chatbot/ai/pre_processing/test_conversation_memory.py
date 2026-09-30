"""Tests for Phase 58's server-side, in-memory conversation history
(ai/pre_processing/conversation_memory.py) - no real client/LLM involved."""

from langchain_core.messages import AIMessage, HumanMessage

from src.hrb_chatbot.ai.pre_processing import conversation_memory


def setup_function():
    # The store is a plain module-level dict - clear it between tests so
    # one test's conversation_id can't leak into another's assertions.
    conversation_memory._CONVERSATIONS.clear()


def test_unknown_conversation_id_returns_empty_history():
    assert conversation_memory.load_history("never-seen-before") == []


def test_new_conversation_id_returns_a_non_empty_string():
    first = conversation_memory.new_conversation_id()
    second = conversation_memory.new_conversation_id()

    assert first and second
    assert first != second


def test_save_turn_then_load_history_round_trips_as_human_then_ai_message():
    conversation_memory.save_turn("conv-1", "what database issues have we had?", "Two timeout tickets.")

    history = conversation_memory.load_history("conv-1")

    assert history == [
        HumanMessage(content="what database issues have we had?"),
        AIMessage(content="Two timeout tickets."),
    ]


def test_multiple_turns_accumulate_in_order():
    conversation_memory.save_turn("conv-1", "question one", "answer one")
    conversation_memory.save_turn("conv-1", "question two", "answer two")

    history = conversation_memory.load_history("conv-1")

    assert [message.content for message in history] == ["question one", "answer one", "question two", "answer two"]


def test_different_conversation_ids_stay_isolated():
    conversation_memory.save_turn("conv-a", "a question", "a answer")
    conversation_memory.save_turn("conv-b", "b question", "b answer")

    assert [m.content for m in conversation_memory.load_history("conv-a")] == ["a question", "a answer"]
    assert [m.content for m in conversation_memory.load_history("conv-b")] == ["b question", "b answer"]
