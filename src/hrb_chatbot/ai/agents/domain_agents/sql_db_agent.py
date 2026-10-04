"""SQL DB Agent - multi-agentic-rag's domain agent stub. No structured HR
operational database exists yet (see RAG-ROADMAP.md Phase 64, BACKLOG.md) -
reports that honestly rather than inventing a result."""

NOT_AVAILABLE_MESSAGE = (
    "The SQL DB Agent isn't available yet - there's no structured HR operational "
    "database wired up for this project. This part of the question couldn't be answered."
)


async def run(focus: str) -> str:
    return NOT_AVAILABLE_MESSAGE
