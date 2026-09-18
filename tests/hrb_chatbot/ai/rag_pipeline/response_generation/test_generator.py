"""Tests for generate_answer() (ai/rag_pipeline/response_generation/response_generator.py).
Covers: no-chunks short-circuits without calling the LLM (saves money on a
question the KB has no relevant content for), the grounding instructions
and filenames actually reach the prompt, and model_name correctly picks
between the shared client and a fresh one-off override. Uses fakes from
conftest.py - no real network call."""

from src.hrb_chatbot.ai.rag_pipeline.response_generation import response_generator
from tests.conftest import FakeChatClient, FakeClientGateway

SAMPLE_CHUNKS = [
    {"document_id": "doc-1", "filename": "policy.pdf", "chunk_index": 0, "text": "Leave is 16 weeks.", "score": 0.9}
]


def test_no_chunks_returns_the_no_context_answer_without_calling_the_llm(monkeypatch):
    fake_chat = FakeChatClient()
    monkeypatch.setattr(response_generator, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat))

    result = response_generator.generate_answer("any question", chunks=[])

    assert result["answer"] == response_generator.NO_CONTEXT_ANSWER
    assert fake_chat.calls == []  # never called - no chunks means nothing to ground on


def test_generate_answer_uses_the_shared_client_when_no_model_override(monkeypatch):
    fake_chat = FakeChatClient(model="gpt-4.1-mini", answer="16 weeks of parental leave.")
    monkeypatch.setattr(response_generator, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat))

    result = response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    assert result["answer"] == "16 weeks of parental leave."
    assert result["model_used"] == "gpt-4.1-mini"
    assert len(fake_chat.calls) == 1


def test_context_cites_filename_and_chunk_index(monkeypatch):
    fake_chat = FakeChatClient()
    monkeypatch.setattr(response_generator, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat))

    response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    context = fake_chat.calls[0]["context"]
    assert "policy.pdf" in context
    assert "chunk 0" in context
    assert "Leave is 16 weeks." in context


def test_question_carries_the_grounding_instruction(monkeypatch):
    fake_chat = FakeChatClient()
    monkeypatch.setattr(response_generator, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat))

    response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    question = fake_chat.calls[0]["question"]
    assert "ONLY the context" in question
    assert "say you don't know" in question
    assert "How much leave?" in question


def test_model_name_override_builds_a_fresh_client_not_the_shared_one(monkeypatch):
    built_with_model = []

    def fake_openai_chat_client(model=None):
        built_with_model.append(model)
        return FakeChatClient(model=model, answer="overridden-model answer")

    monkeypatch.setattr(response_generator, "OpenAIChatClient", fake_openai_chat_client)
    # No client gateway patched - if the code path is wrong and falls back to
    # the shared gateway, this would raise instead of silently passing.
    monkeypatch.setattr(response_generator, "get_client_gateway", lambda: (_ for _ in ()).throw(AssertionError(
        "should not use the shared gateway when model_name overrides it"
    )))

    result = response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS, model_name="gpt-4.1-nano")

    assert built_with_model == ["gpt-4.1-nano"]
    assert result["model_used"] == "gpt-4.1-nano"
    assert result["answer"] == "overridden-model answer"
