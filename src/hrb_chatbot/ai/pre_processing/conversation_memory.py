"""Server-side, in-process conversation history for multi-turn support -
keyed by conversation_id, timestamped. In-memory for now; a cache DB is planned later, not built here."""

import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# {conversation_id: [{"role": "human"|"ai", "content": str, "timestamp": str}, ...]}
_CONVERSATIONS: dict[str, list[dict]] = {}


def new_conversation_id() -> str:
    return uuid.uuid4().hex


def load_history(conversation_id: str) -> list[BaseMessage]:
    """Returns [] for an unknown/new conversation_id - never raises."""
    turns = _CONVERSATIONS.get(conversation_id, [])
    messages: list[BaseMessage] = []
    for turn in turns:
        if turn["role"] == "human":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))
    return messages


def save_turn(conversation_id: str, human_content: str, ai_content: str) -> None:
    now = datetime.now(UTC).isoformat()
    turns = _CONVERSATIONS.setdefault(conversation_id, [])
    turns.append({"role": "human", "content": human_content, "timestamp": now})
    turns.append({"role": "ai", "content": ai_content, "timestamp": now})
