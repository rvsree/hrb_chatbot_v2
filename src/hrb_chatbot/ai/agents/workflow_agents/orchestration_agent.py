"""Single-agentic-rag's tool-calling loop - uses ChatOpenAI directly, not GatewayChatModel (see RAG-ROADMAP.md Phase 55)."""

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.ai.rag_pipeline.tools.agentic_tools import (
    AGENTIC_TOOL_DEFINITIONS,
    get_leave_balance_tool,
    get_leave_history_tool,
    search_knowledge_base,
)
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("agents.orchestration_agent")

DEFAULT_MAX_ITERATIONS = 5

SYSTEM_PROMPT = """You are the HR benefits assistant for JPMorgan Chase employees.
You have access to tools - use them to answer the question, don't guess.
For policy/benefits questions, use SearchKnowledgeBase.
For the caller's own leave balance or leave history, use GetLeaveBalance/GetLeaveHistory.
Only answer from what the tools return - never invent a policy detail or a balance number."""

TOOL_FUNCTIONS = {
    # SearchKnowledgeBase also takes the tool call's own search_strategy arg (the agent's own choice).
    "SearchKnowledgeBase": lambda args, employee_id: search_knowledge_base(
        args.get("input", ""), args.get("search_strategy")
    ),
    "GetLeaveBalance": lambda args, employee_id: get_leave_balance_tool(employee_id),
    "GetLeaveHistory": lambda args, employee_id: get_leave_history_tool(employee_id),
}


def _build_llm() -> ChatOpenAI:
    api_key = read_setting(None, "OPENAI_API_KEY")
    base_url = read_url_setting(None, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = read_setting(None, "OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0)


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
        history = conversation_memory.load_history(resolved_conversation_id)

    messages = [SystemMessage(content=SYSTEM_PROMPT), *history, HumanMessage(content=query)]
    tools_used = []

    for i in range(resolved_max_iterations):
        response = await llm.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            if resolved_conversation_id:
                conversation_memory.save_turn(resolved_conversation_id, query, response.content)
            return {
                "answer": response.content,
                "tools_used": tools_used,
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

            logger.info("Agent called tool=%s input=%r args=%r", tool_name, tool_input[:80], tool_args)
            messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    # Not saved to history - a failure message isn't worth remembering as
    # context for the caller's next turn, unlike a real final answer above.
    return {
        "answer": "I wasn't able to finish reasoning about this within the allowed number of steps. Please rephrase or ask a more specific question.",
        "tools_used": tools_used,
        "iterations": resolved_max_iterations,
        "conversation_id": resolved_conversation_id,
    }
