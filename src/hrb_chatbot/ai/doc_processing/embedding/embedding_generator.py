"""Turns chunk texts into embedding vectors - checks the embedding cache
first (Phase 77), only the real cache misses go to the embedding API, in
one batched call."""

from src.hrb_chatbot.common.clients.cache_client.embedding_cache import hash_text
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.embedding")

DEFAULT_EMBED_MODEL = "text-embedding-3-small"


async def generate_embeddings(chunks: list[str], embedding_model: str | None = None) -> list[list[float]]:
    """Return one embedding vector per chunk, in order. `embedding_model`
    overrides OPENAI_EMBED_MODEL - see get_embeddings() for the dimension-mismatch risk."""
    if not chunks:
        return []

    resolved_model = embedding_model or read_setting(None, "OPENAI_EMBED_MODEL", DEFAULT_EMBED_MODEL)
    cache = get_db_gateway().embedding_cache()

    content_hashes = [hash_text(chunk) for chunk in chunks]
    cached = await cache.get_many(content_hashes, resolved_model)

    missing_indexes = [i for i, content_hash in enumerate(content_hashes) if content_hash not in cached]
    if missing_indexes:
        missing_chunks = [chunks[i] for i in missing_indexes]
        fresh_embeddings = get_client_gateway().openai_embedding().get_embeddings(
            missing_chunks, model=resolved_model
        )
        new_entries = [
            (content_hashes[i], embedding) for i, embedding in zip(missing_indexes, fresh_embeddings, strict=True)
        ]
        await cache.set_many(new_entries, resolved_model)
        for i, embedding in zip(missing_indexes, fresh_embeddings, strict=True):
            cached[content_hashes[i]] = embedding

    embeddings = [cached[content_hash] for content_hash in content_hashes]
    logger.info(
        "Generated %d embedding(s) (%d cache hit(s), %d cache miss(es), dimension %d)",
        len(embeddings),
        len(chunks) - len(missing_indexes),
        len(missing_indexes),
        len(embeddings[0]),
    )
    return embeddings
