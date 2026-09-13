"""Turns chunk texts into embedding vectors.

Thin on purpose: the real work is OpenAIEmbeddingClient.get_embeddings();
this just names the one call so pipeline.py doesn't reach into the client
gateway directly.
"""

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.embedding")


def generate_embeddings(chunks: list[str], embedding_model: str | None = None) -> list[list[float]]:
    """Return one embedding vector per chunk, in the same order as chunks.

    `embedding_model` overrides OPENAI_EMBED_MODEL for this call only - see
    get_embeddings()'s docstring for the dimension-mismatch risk.
    """
    if not chunks:
        return []

    embeddings = get_client_gateway().openai_embedding().get_embeddings(chunks, model=embedding_model)
    logger.info("Generated %d embeddings (dimension %d)", len(embeddings), len(embeddings[0]))
    return embeddings
