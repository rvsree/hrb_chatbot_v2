"""Generates a grounded answer from retrieved chunks - a real LCEL chain
(ChatPromptTemplate | GatewayChatModel | result-mapper), matching the IK
cohort's own Module 4 pattern instead of a hand-rolled ask() call."""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.clients.llm_client.langchain_chat_model import GatewayChatModel
from src.hrb_chatbot.common.enums import LlmProvider
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.response_generator")

NO_CONTEXT_ANSWER = "I don't have any information about that in the knowledge base."

# {context} lives inside the system message alongside the grounding rules
# - matches Module 4's own worked example (rules + evidence share one
# privileged channel; the human message carries only the bare question).
SYSTEM_PROMPT_TEMPLATE = (
    "You are the HR benefits assistant for JPMC employees. Use ONLY the "
    "context below to answer - if the answer isn't in it, say you don't "
    "know rather than guessing. Never invent information not present in "
    "the context.\n\nContext:\n{context}"
)

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_TEMPLATE),
        ("human", "{question}"),
    ]
)


def _build_context(chunks: list[dict]) -> str:
    """One block per chunk, labeled with its source filename so the model's
    own answer can reference where a fact came from."""
    blocks = []
    for chunk in chunks:
        blocks.append(f"[{chunk['filename']}, chunk {chunk['chunk_index']}]\n{chunk['text']}")
    return "\n\n".join(blocks)


def _to_result(message: AIMessage) -> dict:
    # GatewayChatModel sets response_metadata["model"] - StrOutputParser()
    # alone would discard it, and this app's response needs model_used too.
    return {"answer": message.content, "model_used": message.response_metadata.get("model", "unknown")}


def generate_answer(
    query: str,
    chunks: list[dict],
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Returns {"answer": str, "model_used": str} - model_used is the
    actually-resolved model."""
    if not chunks:
        logger.info("No chunks retrieved for %r - returning the no-context answer, not calling the LLM", query)
        return {"answer": NO_CONTEXT_ANSWER, "model_used": model_name or get_client_gateway().openai_chat().model}

    llm = GatewayChatModel(
        provider=LlmProvider.OPENAI,
        temperature=temperature,
        model_name_override=model_name,
        max_tokens=max_tokens,
    )
    chain = RAG_PROMPT | llm | RunnableLambda(_to_result)

    context = _build_context(chunks)
    result = chain.invoke({"context": context, "question": query})

    logger.info("Generated a %d-character answer from %d chunk(s)", len(result["answer"]), len(chunks))
    return result
