"""Web Search Agent - multi-agentic-rag's domain agent for external/current
information the internal KB and HR systems can't answer (Phase 70). Thin
wrapper over the existing Tavily client - never raises, same convention as
every other domain agent."""

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway


async def run(focus: str) -> str:
    result = get_client_gateway().tavily().search(focus)

    if result.get("error"):
        return f"Error: web search failed ({result['error']})."

    if not result["results"] and not result["answer"]:
        return "No relevant web search results found."

    output = ""
    if result["answer"]:
        output += f"{result['answer']}\n\n"

    for i, item in enumerate(result["results"], 1):
        title = item.get("title", "")
        snippet = item.get("content", "")
        url = item.get("url", "")
        output += f"--- Web Source {i} ({title}) ---\n{snippet}\n({url})\n\n"

    return output.strip()
