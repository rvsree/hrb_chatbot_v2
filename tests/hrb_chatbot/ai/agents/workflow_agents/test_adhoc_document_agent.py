"""Tests for Phase 136's ReAct loop - the LLM is faked (no real API call),
matching test_orchestration_agent.py's own established pattern. The real
behavior under test: ReadDocument only ever returns from the file_texts
dict passed in (no vector store, no MCP, nothing else it could call), and
SendEmailWithAnswer only fires when the agent actually calls it."""

from src.hrb_chatbot.ai.agents.workflow_agents import adhoc_document_agent


class FakeResponse:
    def __init__(self, content="", tool_calls=None, model_name="gpt-4.1-mini-fake"):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        self.model_name = model_name


class FakeLlm:
    def __init__(self, responses):
        self._responses = list(responses)
        self.model_name = "gpt-4.1-mini-fake"

    async def ainvoke(self, messages):
        return self._responses.pop(0)


def _patch_llm(monkeypatch, responses):
    monkeypatch.setattr(adhoc_document_agent, "_build_llm", lambda: FakeLlm(responses))


async def test_answers_without_a_tool_call_in_one_iteration(monkeypatch):
    _patch_llm(monkeypatch, [FakeResponse(content="Hi there!")])

    result = await adhoc_document_agent.run_agent("hello", {"a.pdf": "some text"})

    assert result["answer"] == "Hi there!"
    assert result["files_used"] == []
    assert result["iterations"] == 1
    assert result["llm_call_count"] == 1


async def test_read_document_tool_returns_the_real_file_text(monkeypatch):
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(tool_calls=[{"name": "ReadDocument", "args": {"filename": "policy.pdf"}, "id": "call-1"}]),
            FakeResponse(content="16 weeks, per the document."),
        ],
    )

    result = await adhoc_document_agent.run_agent(
        "How much parental leave?", {"policy.pdf": "Parental leave is 16 weeks."}
    )

    assert result["answer"] == "16 weeks, per the document."
    assert result["files_used"] == ["policy.pdf"]


async def test_read_document_for_an_unattached_filename_returns_an_error_to_the_agent(monkeypatch):
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(tool_calls=[{"name": "ReadDocument", "args": {"filename": "nope.pdf"}, "id": "call-1"}]),
            FakeResponse(content="I don't have access to that file."),
        ],
    )

    result = await adhoc_document_agent.run_agent("question", {"policy.pdf": "real text"})

    assert result["files_used"] == []
    assert result["answer"] == "I don't have access to that file."


async def test_send_email_tool_sets_email_sent_to_on_success(monkeypatch):
    async def _fake_send_email_success(recipient, subject, body):
        return {"sent": True, "message": f"Email sent to {recipient}."}

    # send_email is synchronous in the real module - patch it as a plain function, not async.
    monkeypatch.setattr(adhoc_document_agent, "send_email", lambda recipient, subject, body: {"sent": True, "message": f"Email sent to {recipient}."})
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(
                tool_calls=[
                    {
                        "name": "SendEmailWithAnswer",
                        "args": {"recipient_email": "someone@example.com", "answer": "The answer."},
                        "id": "call-1",
                    }
                ]
            ),
            FakeResponse(content="Done - I've emailed the answer."),
        ],
    )

    result = await adhoc_document_agent.run_agent("email me the answer", {"a.pdf": "text"})

    assert result["email_sent_to"] == "someone@example.com"


async def test_send_email_tool_sends_the_output_guardrail_checked_text_not_the_raw_text(monkeypatch):
    sent_bodies = []

    def _capturing_send_email(recipient, subject, body):
        sent_bodies.append(body)
        return {"sent": True, "message": f"Email sent to {recipient}."}

    async def _masking_check_output(query, answer):
        return answer.replace("555-12-3456", "<SSN>")

    monkeypatch.setattr(adhoc_document_agent, "send_email", _capturing_send_email)
    monkeypatch.setattr(adhoc_document_agent, "check_output", _masking_check_output)
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(
                tool_calls=[
                    {
                        "name": "SendEmailWithAnswer",
                        "args": {"recipient_email": "someone@example.com", "answer": "SSN on file: 555-12-3456"},
                        "id": "call-1",
                    }
                ]
            ),
            FakeResponse(content="Done - I've emailed the answer."),
        ],
    )

    result = await adhoc_document_agent.run_agent("email me the answer", {"a.pdf": "text"})

    assert result["email_sent_to"] == "someone@example.com"
    assert sent_bodies == ["SSN on file: <SSN>"]


async def test_send_email_tool_failure_leaves_email_sent_to_none(monkeypatch):
    monkeypatch.setattr(
        adhoc_document_agent, "send_email", lambda recipient, subject, body: {"sent": False, "message": "sender not verified"}
    )
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(
                tool_calls=[
                    {
                        "name": "SendEmailWithAnswer",
                        "args": {"recipient_email": "someone@example.com", "answer": "The answer."},
                        "id": "call-1",
                    }
                ]
            ),
            FakeResponse(content="I couldn't send that email."),
        ],
    )

    result = await adhoc_document_agent.run_agent("email me the answer", {"a.pdf": "text"})

    assert result["email_sent_to"] is None


async def test_unknown_tool_name_does_not_crash_the_loop(monkeypatch):
    _patch_llm(
        monkeypatch,
        [
            FakeResponse(tool_calls=[{"name": "SearchTheWeb", "args": {}, "id": "call-1"}]),
            FakeResponse(content="I can't do that."),
        ],
    )

    result = await adhoc_document_agent.run_agent("question", {"a.pdf": "text"})

    assert result["answer"] == "I can't do that."


async def test_exhausting_max_iterations_returns_the_fallback_message(monkeypatch):
    responses = [
        FakeResponse(tool_calls=[{"name": "ReadDocument", "args": {"filename": "a.pdf"}, "id": f"call-{i}"}])
        for i in range(adhoc_document_agent.DEFAULT_MAX_ITERATIONS)
    ]
    _patch_llm(monkeypatch, responses)

    result = await adhoc_document_agent.run_agent("question", {"a.pdf": "text"})

    assert "wasn't able to finish reasoning" in result["answer"]
    assert result["iterations"] == adhoc_document_agent.DEFAULT_MAX_ITERATIONS
