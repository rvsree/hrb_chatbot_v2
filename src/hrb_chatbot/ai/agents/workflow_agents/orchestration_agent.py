"""Single-agentic-rag's tool-calling loop - uses ChatOpenAI directly, not GatewayChatModel (see RAG-ROADMAP.md Phase 55)."""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from src.hrb_chatbot.ai.agents._llm_helpers import AGENT_LLM_TIMEOUT_SECONDS, build_agent_llm
from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.ai.prompts.agent_prompts import ORCHESTRATION_SYSTEM_PROMPT
from src.hrb_chatbot.ai.rag_pipeline.tools.agentic_tools import (
    AGENTIC_TOOL_DEFINITIONS,
    get_leave_balance_tool,
    get_leave_history_tool,
    search_knowledge_base,
)
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("agents.orchestration_agent")

DEFAULT_MAX_ITERATIONS = 5

# Phase 71: moved into ai/prompts/agent_prompts.py - kept as a module-level
# name here too, since this is the agent's own public prompt constant.
SYSTEM_PROMPT = ORCHESTRATION_SYSTEM_PROMPT

TOOL_FUNCTIONS = {
    # SearchKnowledgeBase also takes the tool call's own search_strategy arg (the agent's own choice).
    "SearchKnowledgeBase": lambda args, employee_id: search_knowledge_base(
        args.get("input", ""), args.get("search_strategy")
    ),
    "GetLeaveBalance": lambda args, employee_id: get_leave_balance_tool(employee_id),
    "GetLeaveHistory": lambda args, employee_id: get_leave_history_tool(employee_id),
}


def _build_llm() -> ChatOpenAI:
    return build_agent_llm()


async def run_agent(
    query: str,
    employee_id: str | None,
    max_iterations: int | None = None,
    enable_conversation_memory: bool = False,
    conversation_id: str | None = None,
) -> dict:
    """Runs the tool-calling loop for one query - only the final answer is saved to history."""
    resolved_max_iterations = max_iterations or DEFAULT_MAX_ITERATIONS
    llm = _build_llm().bind(tools=AGENTIC_TOOL_DEFINITIONS)

    resolved_conversation_id = None
    history = []
    if enable_conversation_memory:
        resolved_conversation_id = conversation_id or conversation_memory.new_conversation_id()
        history = await conversation_memory.load_history(resolved_conversation_id)

    messages = [SystemMessage(content=SYSTEM_PROMPT), *history, HumanMessage(content=query)]
    tools_used = []
    tool_outputs = []  # raw tool output text, kept alongside tools_used - needed to eval groundedness (Phase 69)

    for i in range(resolved_max_iterations):
        with log_backend_call(logger, "orchestration_agent", "ainvoke", iteration=i + 1):
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=AGENT_LLM_TIMEOUT_SECONDS)

        if response.usage_metadata:
            logger.info(
                "[orchestration_agent] tokens used: %s prompt + %s completion",
                response.usage_metadata["input_tokens"],
                response.usage_metadata["output_tokens"],
            )

        messages.append(response)

        if not response.tool_calls:
            if resolved_conversation_id:
                await conversation_memory.save_turn(resolved_conversation_id, employee_id, query, response.content)
            return {
                "answer": response.content,
                "tools_used": tools_used,
                "tool_outputs": tool_outputs,
                "iterations": i + 1,
                "conversation_id": resolved_conversation_id,
            }

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_input = tool_args.get("input", "")
            tools_used.append({"tool_name": tool_name, "tool_input": tool_input})

            tool_function = TOOL_FUNCTIONS.get(tool_name)
            if tool_function is None:
                tool_output = f"Error: unknown tool {tool_name!r}"
            else:
                tool_output = await tool_function(tool_args, employee_id)

            tool_outputs.append(tool_output)
            logger.info("Agent called tool=%s input=%r args=%r", tool_name, tool_input[:80], tool_args)
            messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    # Not saved to history - a failure message isn't worth remembering as
    # context for the caller's next turn, unlike a real final answer above.
    return {
        "answer": "I wasn't able to finish reasoning about this within the allowed number of steps. Please rephrase or ask a more specific question.",
        "tools_used": tools_used,
        "tool_outputs": tool_outputs,
        "iterations": resolved_max_iterations,
        "conversation_id": resolved_conversation_id,
    }
