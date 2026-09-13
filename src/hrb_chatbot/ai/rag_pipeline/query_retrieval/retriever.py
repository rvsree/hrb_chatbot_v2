"""Embeds a query, searches the vector store, and returns the matching
chunks with their source document's filename attached (for citations).
"""

from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import COLLECTION_NAME
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.retriever")

# top_k always returns exactly that many results, even when none are
# actually relevant (e.g. a question about a topic nothing indexed covers) -
# vector search has no built-in "good enough" concept. Without a floor, a
# question with no real answer in the KB still returns its "least-bad"
# matches as if they were real sources, alongside a generated answer that
# (correctly) says it doesn't know - misleading, even though the answer
# itself isn't wrong. Empirically calibrated, not guessed: a real query
# against this project's own indexed content scored ~0.69-0.97 (Chroma
# cosine distance, lower=better) for genuinely relevant chunks, and
# ~1.22-1.27 for chunks from an unrelated document once nothing relevant
# was indexed - see docs/RAG-ROADMAP.md for the exact live test. 1.1 sits
# between those two clusters with margin on each side.
MAX_CHROMA_DISTANCE = 1.1
# Pinecone's cosine similarity is the opposite direction (higher=better,
# roughly 0-1) - see pinecone_client.py's module docstring on the
# score/distance inversion. No real Pinecone query has been run against
# this project's own content yet (ChromaDB-first, per the project's own
# testing order), so this is a reasonable starting point, not
# empirically calibrated the way MAX_CHROMA_DISTANCE is - revisit once
# Pinecone is actually exercised live.
MIN_PINECONE_SCORE = 0.5


async def retrieve_chunks(queries: list[str], top_k: int = 5, vector_db: str | None = None) -> list[dict]:
    """Embed each query, search the vector store for each, and return the merged
    chunks - deduplicated by (document_id, chunk_index) so the same chunk found
    by two different sub-queries is only returned once. Each result has
    document_id, filename, chunk_index, text, score (models/rag.py's RetrievedChunk)."""
    db_gateway = get_db_gateway()
    vector_store = db_gateway.vector_store(provider=vector_db)
    embedding_client = get_client_gateway().openai_embedding()

    chunks: list[dict] = []
    seen_chunk_keys: set[tuple] = set()

    for query in queries:
        query_embedding = embedding_client.get_embeddings([query])[0]
        # $ne (not equal), not an is_current=True equality match: chunks
        # indexed before this field existed have no is_current key at all,
        # and an equality filter would silently exclude them too. Only a
        # chunk explicitly flipped to False (superseded) should be excluded.
        results = vector_store.query(
            collection_name=COLLECTION_NAME,
            query_embedding=query_embedding,
            top_k=top_k,
            where={"is_current": {"$ne": False}},
        )

        # Nested once, per ChromaDBClient/PineconeClient.query()'s shape -
        # [0] is "for the one query embedding we sent."
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        scores = results["distances"][0]

        for _chunk_id, text, metadata, score in zip(ids, documents, metadatas, scores, strict=True):
            if not _meets_relevance_bar(score, vector_store.PROVIDER_NAME):
                continue
            document_id = metadata.get("document_id")
            chunk_index = metadata.get("chunk_index")
            key = (document_id, chunk_index)
            if key in seen_chunk_keys:
                continue
            seen_chunk_keys.add(key)
            chunks.append(
                {"document_id": document_id, "chunk_index": chunk_index, "text": text, "score": score}
            )

    await _attach_filenames(chunks, db_gateway)

    logger.info(
        "Retrieved %d chunk(s) meeting the relevance bar, for %d quer(y/ies)", len(chunks), len(queries)
    )
    return chunks


def _meets_relevance_bar(score: float, provider_name: str) -> bool:
    """True if this chunk is worth keeping - direction depends on the
    backend: Chroma's distance is lower=better, Pinecone's score is
    higher=better (see the module-level constants above)."""
    if provider_name == "pinecone":
        return score >= MIN_PINECONE_SCORE
    return score <= MAX_CHROMA_DISTANCE


async def _attach_filenames(chunks: list[dict], db_gateway) -> None:
    """Look up each chunk's source document filename, one metadata-store call
    per distinct document_id (not per chunk) - a query typically retrieves
    several chunks from the same document."""
    metadata_store = db_gateway.metadata_store()
    filenames_by_document_id: dict[str, str] = {}

    for chunk in chunks:
        document_id = chunk["document_id"]
        if document_id not in filenames_by_document_id:
            document = await metadata_store.get_document(document_id)
            filenames_by_document_id[document_id] = document["filename"] if document else "unknown"
        chunk["filename"] = filenames_by_document_id[document_id]
