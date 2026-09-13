"""Searches the vector store for chunks matching a query - workshop
Module 4 (LangChain), against whichever store RAG_VECTOR_DB selects:
ChromaDB or Pinecone. Two plain functions, one per technique - no
classes/interfaces, matching how the workshop's own demo.py is written.
"""

import json

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import COLLECTION_NAME
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.retriever")

# Only chunks still "in play" are ever returned - $ne (not equal), not an
# is_current=True equality match: chunks indexed before this field existed
# have no is_current key at all, and an equality filter would silently
# exclude those too. Only a chunk explicitly flipped to False (superseded)
# should be excluded.
CURRENT_CHUNKS_ONLY = {"is_current": {"$ne": False}}

# top_k always returns exactly that many results, even when none are
# actually relevant - vector search has no built-in "good enough" concept.
# Empirically calibrated, not guessed: see docs/RAG-ROADMAP.md's Phase 4.5
# entry for the real query that produced these two numbers. Only applied to
# similarity search, which has a real per-chunk score to compare against -
# LangChain's max_marginal_relevance_search() does not return scores at all.
MAX_CHROMA_DISTANCE = 1.1
MIN_PINECONE_SCORE = 0.5


class _TextBackfillPineconeIndex:
    """Wraps a real pinecone.Index so LangChain's PineconeVectorStore (which
    expects chunk text under a plain "text" metadata key, and does a hard,
    unguarded metadata.pop("text") in its MMR code path specifically -
    confirmed live: a KeyError, not a graceful skip like its similarity-
    search path uses) still works against data written two different older
    ways: LlamaIndex (ai/doc_processing/indexing/vector_indexer.py, Phase 3)
    stores text inside a "_node_content" JSON blob; the original hand-
    written indexer (before this rewrite) stored it under "document"
    (pinecone_client.py's own convention). Both kinds of vectors can be
    live in the same namespace during this transition, so both are handled
    here - "text" is always guaranteed present afterward, empty string as
    the last resort, so LangChain's unguarded pop() never raises."""

    def __init__(self, real_index):
        self._real_index = real_index

    def __getattr__(self, name):
        return getattr(self._real_index, name)

    def query(self, *args, **kwargs):
        response = self._real_index.query(*args, **kwargs)
        for match in response.matches:
            if not match.metadata or "text" in match.metadata:
                continue
            match.metadata["text"] = self._extract_text(match.metadata)
        return response

    @staticmethod
    def _extract_text(metadata: dict) -> str:
        if "_node_content" in metadata:
            try:
                return json.loads(metadata["_node_content"]).get("text", "")
            except (json.JSONDecodeError, AttributeError):
                return ""
        if "document" in metadata:
            return metadata["document"]
        return ""


def _embeddings() -> OpenAIEmbeddings:
    api_key = read_setting(None, "OPENAI_API_KEY")
    base_url = read_url_setting(None, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    embedding_model = read_setting(None, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
    return OpenAIEmbeddings(api_key=api_key, base_url=base_url, model=embedding_model)


def _vector_store(vector_db: str | None):
    """Return (LangChain vector store, resolved provider name), wrapping
    this project's already-connected ChromaDB/Pinecone client's raw
    collection/index object - reads the exact same physical collection/
    namespace ai/doc_processing/indexing/vector_indexer.py writes into."""
    vector_store_client = get_db_gateway().vector_store(provider=vector_db)
    embeddings = _embeddings()

    if vector_store_client.PROVIDER_NAME == "pinecone":
        wrapped_index = _TextBackfillPineconeIndex(vector_store_client.get_index())
        store = PineconeVectorStore(index=wrapped_index, embedding=embeddings, namespace=COLLECTION_NAME)
    else:
        store = Chroma(
            client=vector_store_client.get_client(),
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
        )

    return store, vector_store_client.PROVIDER_NAME


def _meets_relevance_bar(score: float, provider_name: str) -> bool:
    # Direction depends on the backend: Chroma's distance is lower=better,
    # Pinecone's score is higher=better.
    if provider_name == "pinecone":
        return score >= MIN_PINECONE_SCORE
    return score <= MAX_CHROMA_DISTANCE


def _document_to_chunk(document: Document, score: float | None) -> dict:
    metadata = document.metadata
    return {
        "document_id": metadata.get("document_id"),
        "chunk_index": metadata.get("chunk_index"),
        "text": document.page_content,
        "score": score,
    }


def search_similarity(query: str, top_k: int = 5, vector_db: str | None = None) -> list[dict]:
    # Plain relevance-ranked search - the default, matching module 4's
    # own "start here" recommendation. Chunks below the relevance bar
    # (see MAX_CHROMA_DISTANCE/MIN_PINECONE_SCORE above) are dropped.
    store, provider = _vector_store(vector_db)
    results = store.similarity_search_with_score(query, k=top_k, filter=CURRENT_CHUNKS_ONLY)

    chunks = []
    for document, score in results:
        if _meets_relevance_bar(score, provider):
            chunks.append(_document_to_chunk(document, score))
    return chunks


def search_mmr(query: str, top_k: int = 5, vector_db: str | None = None, fetch_k: int | None = None) -> list[dict]:
    # Max Marginal Relevance - balances relevance with diversity, so the
    # results aren't all near-duplicates of each other (module 2's own
    # "rule of thumb": use this when you want non-redundant context, often
    # better for RAG prompts than plain similarity). fetch_k (how many
    # candidates to consider before picking the diverse top_k) defaults to
    # 3x top_k, the same ratio module 4's own notes recommend.
    store, provider = _vector_store(vector_db)
    documents = store.max_marginal_relevance_search(
        query, k=top_k, fetch_k=fetch_k or top_k * 3, filter=CURRENT_CHUNKS_ONLY
    )
    # LangChain's max_marginal_relevance_search() does not return a score at
    # all (unlike similarity_search_with_score) - None here, not a made-up
    # number, and no relevance-bar filtering for the same reason.
    return [_document_to_chunk(document, None) for document in documents]


SEARCH_STRATEGIES = {
    "similarity": search_similarity,
    "mmr": search_mmr,
}


async def retrieve_chunks(
    queries: list[str], top_k: int = 5, vector_db: str | None = None, search_strategy: str | None = None
) -> list[dict]:
    """Search for each query and return the merged chunks - deduplicated by
    (document_id, chunk_index) so the same chunk found by two different
    sub-queries is only returned once. Each result has document_id,
    filename, chunk_index, text, score (models/rag.py's RetrievedChunk;
    score is null for MMR results, which have no per-chunk score)."""
    resolved_strategy = search_strategy or "similarity"
    logger.info("search: strategy=%s (%s)", resolved_strategy, "explicit" if search_strategy else "default")
    if resolved_strategy not in SEARCH_STRATEGIES:
        raise ValueError(f"Unknown search_strategy {resolved_strategy!r} - choose one of {list(SEARCH_STRATEGIES)}")
    search_function = SEARCH_STRATEGIES[resolved_strategy]

    db_gateway = get_db_gateway()
    chunks: list[dict] = []
    seen_chunk_keys: set[tuple] = set()

    for query in queries:
        for chunk in search_function(query, top_k=top_k, vector_db=vector_db):
            key = (chunk["document_id"], chunk["chunk_index"])
            if key in seen_chunk_keys:
                continue
            seen_chunk_keys.add(key)
            chunks.append(chunk)

    await _attach_filenames(chunks, db_gateway)

    logger.info(
        "Retrieved %d chunk(s) via %s, for %d quer(y/ies)", len(chunks), resolved_strategy, len(queries)
    )
    return chunks


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
