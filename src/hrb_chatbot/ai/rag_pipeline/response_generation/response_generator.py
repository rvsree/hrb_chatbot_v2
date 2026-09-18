"""Generates a grounded answer from retrieved chunks - the role and the
anti-hallucination instruction live in SYSTEM_PROMPT, sent as each
provider's own native system message/parameter."""

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.clients.llm_client.openai_client import OpenAIChatClient
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.response_generator")

NO_CONTEXT_ANSWER = "I don't have any information about that in the knowledge base."

SYSTEM_PROMPT = (
    "You are the HR benefits assistant for JPMC employees. Answer using ONLY "
    "the context provided with each question - if the answer isn't contained "
    "in that context, say you don't know rather than guessing. Never invent "
    "information not present in the context."
)


def _build_context(chunks: list[dict]) -> str:
    """One block per chunk, labeled with its source filename so the model's
    own answer can reference where a fact came from."""
    blocks = []
    for chunk in chunks:
        blocks.append(f"[{chunk['filename']}, chunk {chunk['chunk_index']}]\n{chunk['text']}")
    return "\n\n".join(blocks)


def generate_answer(
    query: str,
    chunks: list[dict],
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Generate a grounded answer from chunks. Returns {"answer": str,
    "model_used": str} - model_used is the actually-resolved model."""
    if not chunks:
        logger.info("No chunks retrieved for %r - returning the no-context answer, not calling the LLM", query)
        return {"answer": NO_CONTEXT_ANSWER, "model_used": model_name or get_client_gateway().openai_chat().model}

    # model_name overrides OPENAI_CHAT_MODEL for this call only - ask() has
    # no per-call model param, so a fresh client is built instead of the shared gateway.
    if model_name:
        chat_client = OpenAIChatClient(model=model_name)
    else:
        chat_client = get_client_gateway().openai_chat()

    context = _build_context(chunks)

    answer = chat_client.ask(
        query, context=context, system_prompt=SYSTEM_PROMPT, temperature=temperature, max_tokens=max_tokens
    )
    logger.info("Generated a %d-character answer from %d chunk(s)", len(answer), len(chunks))
    return {"answer": answer, "model_used": chat_client.model}
