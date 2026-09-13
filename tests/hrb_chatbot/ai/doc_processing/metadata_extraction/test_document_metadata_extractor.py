"""Tests for extract_document_metadata() (ai/doc_processing/metadata_extraction/
document_metadata_extractor.py). Covers: a clean JSON response, a response
wrapped in prose/markdown fences (a real thing models do despite instructions
not to), and that any failure returns the all-None result rather than
raising - metadata extraction must never be able to fail an index. Uses
FakeChatClient from conftest.py - no real network call."""

from src.hrb_chatbot.ai.doc_processing.metadata_extraction import document_metadata_extractor as extractor
from tests.conftest import FakeChatClient, FakeClientGateway


def test_clean_json_response_is_parsed_correctly(monkeypatch):
    answer = (
        '{"owner": "Jane Smith", "department": "HR", '
        '"doc_type": "policy", "purpose": "Describes paid time off."}'
    )
    monkeypatch.setattr(extractor, "get_client_gateway", lambda: FakeClientGateway(chat_client=FakeChatClient(answer=answer)))

    result = extractor.extract_document_metadata("Some real document text about time off.")

    assert result == {
        "owner": "Jane Smith",
        "department": "HR",
        "doc_type": "policy",
        "purpose": "Describes paid time off.",
    }


def test_json_wrapped_in_prose_and_markdown_fence_is_still_parsed(monkeypatch):
    answer = 'Sure, here is the JSON:\n```json\n{"owner": null, "department": "Finance", "doc_type": "investment", "purpose": null}\n```\nHope that helps!'
    monkeypatch.setattr(extractor, "get_client_gateway", lambda: FakeClientGateway(chat_client=FakeChatClient(answer=answer)))

    result = extractor.extract_document_metadata("Some document text.")

    assert result["department"] == "Finance"
    assert result["doc_type"] == "investment"
    assert result["owner"] is None
    assert result["purpose"] is None


def test_garbage_response_returns_all_none_not_a_crash(monkeypatch):
    monkeypatch.setattr(
        extractor, "get_client_gateway", lambda: FakeClientGateway(chat_client=FakeChatClient(answer="not json at all"))
    )

    result = extractor.extract_document_metadata("Some document text.")

    assert result == extractor.EMPTY_RESULT


def test_empty_document_text_short_circuits_without_calling_the_llm(monkeypatch):
    fake_chat = FakeChatClient()
    monkeypatch.setattr(extractor, "get_client_gateway", lambda: FakeClientGateway(chat_client=fake_chat))

    result = extractor.extract_document_metadata("   ")

    assert result == extractor.EMPTY_RESULT
    assert fake_chat.calls == []


def test_an_exception_from_the_llm_call_is_swallowed_not_raised(monkeypatch):
    def _raise_gateway():
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(extractor, "get_client_gateway", _raise_gateway)

    result = extractor.extract_document_metadata("Some document text.")

    assert result == extractor.EMPTY_RESULT
