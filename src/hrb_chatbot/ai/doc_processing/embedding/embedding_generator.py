"""Turns chunk texts into embedding vectors.

Workshop Module 1 covers what an embedding actually is and how similarity
between two of them is measured. This module is thin on purpose - the real
work is `OpenAIEmbeddingClient.get_embeddings()`, already built and tested
in common/clients/llm_client/openai_client.py; this just names the one call
the indexing pipeline needs, so pipeline.py doesn't reach into the client
gateway directly.
"""

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.embedding")


def generate_embeddings(chunks: list[str], embedding_model: str | None = None) -> list[list[float]]:
    """Return one embedding vector per chunk, in the same order as chunks.

    `embedding_model` overrides OPENAI_EMBED_MODEL for this call only - see
    OpenAIEmbeddingClient.get_embeddings()'s docstring for the dimension-
    mismatch risk that comes with actually using this.
    """
    if not chunks:
        return []

    embeddings = get_client_gateway().openai_embedding().get_embeddings(chunks, model=embedding_model)
    logger.info("Generated %d embeddings (dimension %d)", len(embeddings), len(embeddings[0]))
    return embeddings
