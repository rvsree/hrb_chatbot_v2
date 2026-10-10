"""Phase 136 - the Chat GenAI Workflow's own ReAct tool-calling loop.
Deliberately separate from orchestration_agent.py (single-agentic-rag):
this agent's tool list has exactly 2 entries, neither of which touches a
vector store, MCP, or the web - LLM calls and the attached files' own text
only. See docs/dev-reference/genai_chat_workflow.md for the full design."""

import asyncio
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from src.hrb_chatbot.ai.agents._llm_helpers import AGENT_LLM_TIMEOUT_SECONDS, build_agent_llm
from src.hrb_chatbot.ai.rag_pipeline.response_generation.guardrails_output import check_output
from src.hrb_chatbot.common.clients.email_client.ses_client import send_email
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("agents.adhoc_document_agent")

DEFAULT_MAX_ITERATIONS = 5

SYSTEM_PROMPT_TEMPLATE = """You are answering a question about documents the user just attached directly to this chat - not the HR knowledge base.

Attached files: {filenames}

Use the ReadDocument tool to read a file's content before answering - never
guess at what a file contains. Answer only from what you actually read in
the attached files; if the files don't contain the answer, say so plainly
rather than inventing one. If the user asked you to email the answer to
someone, call SendEmailWithAnswer after you've written your final answer,
with that answer as the email body."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "ReadDocument",
            "description": "Read one attached file's extracted text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Exact filename of the attached file to read."},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "SendEmailWithAnswer",
            "description": "Email the final answer to someone - only call this if the user explicitly asked for the answer to be emailed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_email": {"type": "string", "description": "The email address to send the answer to."},
                    "answer": {"type": "string", "description": "The final answer text to send as the email body."},
                },
                "required": ["recipient_email", "answer"],
            },
        },
    },
]


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 1)


def _build_llm():
    return build_agent_llm().bind(tools=TOOL_DEFINITIONS)


async def run_agent(question: str, file_texts: dict[str, str]) -> dict:
    """file_texts: {filename: extracted_text}. Returns
    {answer, files_used, email_sent_to, model_used, iterations,
    llm_call_count, token_usage, latency_ms}. Never calls a vector store,
    MCP, or web search - ReadDocument only ever reads from file_texts,
    nothing else exists for it to call."""
    started_at = time.perf_counter()
    llm = _build_llm()

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(filenames=", ".join(file_texts.keys()))
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=question)]

    files_used: list[str] = []
    email_sent_to: str | None = None
    total_prompt_tokens = 0
    total_completion_tokens = 0
    llm_call_count = 0

    def _token_usage() -> dict | None:
        if llm_call_count == 0:
            return None
        return {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
        }

    for i in range(DEFAULT_MAX_ITERATIONS):
        with log_backend_call(logger, "adhoc_document_agent", "ainvoke", iteration=i + 1):
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=AGENT_LLM_TIMEOUT_SECONDS)
        llm_call_count += 1

        if response.usage_metadata:
            total_prompt_tokens += response.usage_metadata["input_tokens"]
            total_completion_tokens += response.usage_metadata["output_tokens"]

        messages.append(response)

        if not response.tool_calls:
            return {
                "answer": response.content,
                "files_used": files_used,
                "email_sent_to": email_sent_to,
                "model_used": getattr(llm, "model_name", None) or "unknown",
                "iterations": i + 1,
                "llm_call_count": llm_call_count,
                "token_usage": _token_usage(),
                "latency_ms": {"total": _elapsed_ms(started_at)},
            }

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name == "ReadDocument":
                filename = tool_args.get("filename", "")
                if filename in file_texts:
                    tool_output = file_texts[filename]
                    if filename not in files_used:
                        files_used.append(filename)
                else:
                    tool_output = f"Error: no attached file named {filename!r}. Attached files: {', '.join(file_texts.keys())}."
            elif tool_name == "SendEmailWithAnswer":
                recipient = tool_args.get("recipient_email", "")
                answer_text = tool_args.get("answer", "")
                # Phase 138: the route's own check_output() only runs on the
                # final HTTP response, after run_agent() returns - too late
                # to stop this tool from already having emailed raw,
                # unmasked text. Run the same output rail here, before the
                # email actually goes out.
                safe_answer_text = await check_output(question, answer_text)
                result = send_email(recipient, "Your answer from HR Benefits Chat", safe_answer_text)
                tool_output = result["message"]
                if result["sent"]:
                    email_sent_to = recipient
            else:
                tool_output = f"Error: unknown tool {tool_name!r}"

            logger.info("Agent called tool=%s args=%r", tool_name, {k: v for k, v in tool_args.items() if k != "answer"})
            messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    return {
        "answer": "I wasn't able to finish reasoning about this within the allowed number of steps. Please rephrase or ask a more specific question.",
        "files_used": files_used,
        "email_sent_to": email_sent_to,
        "model_used": getattr(llm, "model_name", None) or "unknown",
        "iterations": DEFAULT_MAX_ITERATIONS,
        "llm_call_count": llm_call_count,
        "token_usage": _token_usage(),
        "latency_ms": {"total": _elapsed_ms(started_at)},
    }
