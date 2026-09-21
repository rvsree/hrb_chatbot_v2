"""Tests for GatewayChatModel (common/clients/llm_client/
langchain_chat_model.py) - adapts this project's own ask() clients to
LangChain's BaseChatModel. Uses FakeChatClient from conftest.py - no real
network call."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.hrb_chatbot.common.clients.llm_client import langchain_chat_model
from src.hrb_chatbot.common.clients.llm_client.langchain_chat_model import GatewayChatModel
from tests.conftest import FakeChatClient, FakeClientGateway


def test_last_message_is_the_question_earlier_message_becomes_context(monkeypatch):
    fake_chat = FakeChatClient(answer="an answer")
    monkeypatch.setattr(
        langchain_chat_model, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat)
    )

    llm = GatewayChatModel(provider="openai")
    result = llm.invoke([HumanMessage(content="earlier turn"), HumanMessage(content="the real question")])

    assert result.content == "an answer"
    call = fake_chat.calls[0]
    assert call["question"] == "the real question"
    assert call["context"] == "earlier turn"
    assert call["system_prompt"] is None


def test_a_system_message_becomes_system_prompt_not_context(monkeypatch):
    fake_chat = FakeChatClient(answer="an answer")
    monkeypatch.setattr(
        langchain_chat_model, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat)
    )

    llm = GatewayChatModel(provider="openai")
    llm.invoke([SystemMessage(content="you are helpful"), HumanMessage(content="the question")])

    call = fake_chat.calls[0]
    assert call["system_prompt"] == "you are helpful"
    assert call["context"] is None
    assert call["question"] == "the question"


def test_response_metadata_carries_which_model_actually_answered(monkeypatch):
    fake_chat = FakeChatClient(model="gpt-4.1-mini", answer="an answer")
    monkeypatch.setattr(
        langchain_chat_model, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat)
    )

    llm = GatewayChatModel(provider="openai")
    result = llm.invoke([HumanMessage(content="the question")])

    assert result.response_metadata["model"] == "gpt-4.1-mini"


def test_model_name_override_builds_a_fresh_openai_client_not_the_shared_gateway(monkeypatch):
    built_with_model = []

    def fake_openai_chat_client(model=None):
        built_with_model.append(model)
        return FakeChatClient(model=model, answer="overridden answer")

    monkeypatch.setattr(langchain_chat_model, "OpenAIChatClient", fake_openai_chat_client)
    monkeypatch.setattr(
        langchain_chat_model,
        "get_client_gateway",
        lambda: (_ for _ in ()).throw(
            AssertionError("should not use the shared gateway when model_name_override is set")
        ),
    )

    llm = GatewayChatModel(provider="openai", model_name_override="gpt-4.1-nano")
    result = llm.invoke([HumanMessage(content="the question")])

    assert built_with_model == ["gpt-4.1-nano"]
    assert result.content == "overridden answer"
    assert result.response_metadata["model"] == "gpt-4.1-nano"


def test_max_tokens_is_passed_through_to_ask(monkeypatch):
    fake_chat = FakeChatClient(answer="an answer")
    monkeypatch.setattr(
        langchain_chat_model, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat)
    )

    llm = GatewayChatModel(provider="openai", max_tokens=200)
    llm.invoke([HumanMessage(content="the question")])

    assert fake_chat.calls[0]["max_tokens"] == 200
