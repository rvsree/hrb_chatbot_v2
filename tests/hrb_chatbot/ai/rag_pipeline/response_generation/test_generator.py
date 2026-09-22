"""Tests for generate_answer() (ai/rag_pipeline/response_generation/
response_generator.py) - a real LCEL chain (ChatPromptTemplate |
GatewayChatModel | result-mapper). Covers: no-chunks short-circuits
without calling the LLM, the grounding instructions and filenames
actually reach the prompt, and model_name is threaded through to
GatewayChatModel. GatewayChatModel is faked the same way
test_retriever.py already fakes it (a BaseChatModel subclass) - no real
network call."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages.ai import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from src.hrb_chatbot.ai.rag_pipeline.response_generation import response_generator

SAMPLE_CHUNKS = [
    {"document_id": "doc-1", "filename": "policy.pdf", "chunk_index": 0, "text": "Leave is 16 weeks.", "score": 0.9}
]


class _FakeGatewayChatModel(BaseChatModel):
    """Stands in for GatewayChatModel - records every prompt it was
    invoked with and returns a canned answer, tagged with whichever
    model it was "built" with (matching response_metadata["model"])."""

    response_text: str = "16 weeks of parental leave."
    model_name_override: str | None = None
    calls: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-gateway"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        generation = ChatGeneration(
            message=AIMessage(
                content=self.response_text,
                response_metadata={"model": self.model_name_override or "gpt-4.1-mini"},
            )
        )
        return ChatResult(generations=[generation])


def test_no_chunks_returns_the_no_context_answer_without_calling_the_llm(monkeypatch):
    fake_llm = _FakeGatewayChatModel()
    monkeypatch.setattr(response_generator, "GatewayChatModel", lambda **kwargs: fake_llm)

    result = response_generator.generate_answer("any question", chunks=[])

    assert result["answer"] == response_generator.NO_CONTEXT_ANSWER
    assert fake_llm.calls == []  # never called - no chunks means nothing to ground on


def test_generate_answer_returns_the_model_that_actually_answered(monkeypatch):
    fake_llm = _FakeGatewayChatModel(response_text="16 weeks of parental leave.")
    monkeypatch.setattr(response_generator, "GatewayChatModel", lambda **kwargs: fake_llm)

    result = response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    assert result["answer"] == "16 weeks of parental leave."
    assert result["model_used"] == "gpt-4.1-mini"
    assert len(fake_llm.calls) == 1


def test_context_cites_filename_and_chunk_index(monkeypatch):
    fake_llm = _FakeGatewayChatModel()
    monkeypatch.setattr(response_generator, "GatewayChatModel", lambda **kwargs: fake_llm)

    response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    system_message = fake_llm.calls[0][0]
    assert "policy.pdf" in system_message.content
    assert "chunk 0" in system_message.content
    assert "Leave is 16 weeks." in system_message.content


def test_system_message_carries_the_grounding_instruction(monkeypatch):
    fake_llm = _FakeGatewayChatModel()
    monkeypatch.setattr(response_generator, "GatewayChatModel", lambda **kwargs: fake_llm)

    response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    system_message, human_message = fake_llm.calls[0]
    assert "ONLY the context" in system_message.content
    assert "say you don't know" in system_message.content
    assert human_message.content == "How much leave?"


def test_system_message_carries_few_shot_examples(monkeypatch):
    # Regression: all 4 examples, including the refusal one, must reach the model.
    fake_llm = _FakeGatewayChatModel()
    monkeypatch.setattr(response_generator, "GatewayChatModel", lambda **kwargs: fake_llm)

    response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS)

    system_message, _ = fake_llm.calls[0]
    assert "Example 1" in system_message.content
    assert "Example 2" in system_message.content
    assert "Example 3" in system_message.content
    assert "Example 4" in system_message.content
    assert "I don't have that information in the available documents" in system_message.content


def test_model_name_override_is_passed_to_gateway_chat_model(monkeypatch):
    captured_kwargs = {}

    def fake_gateway_chat_model(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeGatewayChatModel(
            model_name_override=kwargs.get("model_name_override"), response_text="overridden-model answer"
        )

    monkeypatch.setattr(response_generator, "GatewayChatModel", fake_gateway_chat_model)

    result = response_generator.generate_answer("How much leave?", SAMPLE_CHUNKS, model_name="gpt-4.1-nano")

    assert captured_kwargs["model_name_override"] == "gpt-4.1-nano"
    assert result["model_used"] == "gpt-4.1-nano"
    assert result["answer"] == "overridden-model answer"
