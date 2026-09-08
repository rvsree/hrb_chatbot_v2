"""Orchestrates answering one question against the indexed knowledge base.

THIS FILE IS A SCAFFOLD, NOT AN IMPLEMENTATION
------------------------------------------------
Same pattern as ai/doc_processing/pipeline.py was before it was explicitly
overridden (see docs/RAG-ROADMAP.md - that override does not extend here).
Every function below raises NotImplementedError on purpose. Claude Code's
`POST /rag/query` calls `answer_query()` below; the steps it calls in turn
are yours to write, using the Interview Kickstart workshop's concepts:

    1. decompose_query()  -> ai/pre_processing/query_decompose.py       (Module 4)
       LLM-based, not classical NLP - see docs/RAG-ROADMAP.md Phase 5.1
       for why (a single prompt asking the model to split a complex
       question into 2-4 simpler ones, the same pattern LlamaIndex's own
       SubQuestionQueryEngine uses).
    2. retrieve_chunks()  -> ai/rag_pipeline/query_retrieval/            (Module 4)
    3. generate_answer()  -> ai/rag_pipeline/response_generation/        (Module 4 -
       anti-hallucination/grounding, chain-of-thought prompting)

Replace a stub's body with real logic and its call site in answer_query()
does not need to change - same pattern as PineconeClient's stub next to
ChromaDBClient, and ai/doc_processing/pipeline.py's stubs before them.

What already exists for you to call into
-------------------------------------------
- Embedding the query text: the same client that embeds chunks at index
  time - get_client_gateway().openai_embedding().get_embeddings([query]).
- Querying the vector store: get_db_gateway().vector_store(provider=vector_db)
  .query(collection_name, query_embedding, top_k, where) - already built,
  already tested (common/clients/db_client/chroma_client.py and
  pinecone_client.py). collection_name is
  ai.doc_processing.indexing.vector_indexer.COLLECTION_NAME - the same
  collection/namespace indexing already writes into.
- Generating a response: get_client_gateway().openai_chat().ask(question,
  context=...) - already built, already tested.
"""

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.pipeline")


def decompose_query(query: str) -> list[str]:
    """Break a complex question into simpler sub-questions to retrieve for.

    Returns at least [query] itself when no decomposition is needed - this
    should never return an empty list.
    """
    raise NotImplementedError(
        "decompose_query() is not implemented yet - see ai/pre_processing/"
        "query_decompose.py and docs/RAG-ROADMAP.md Phase 5.1 (LLM-based "
        "decomposition, not classical NLP)."
    )


def retrieve_chunks(
    queries: list[str], top_k: int = 5, vector_db: str | None = None
) -> list[dict]:
    """Embed each query and retrieve the top_k most relevant chunks overall.

    Return one dict per chunk with at least: document_id, chunk_index,
    text, score - matching models/rag.py's RetrievedChunk shape.
    """
    raise NotImplementedError(
        "retrieve_chunks() is not implemented yet - see "
        "ai/rag_pipeline/query_retrieval/. The vector store client already "
        "works: get_db_gateway().vector_store(provider=vector_db).query(...)."
    )


def generate_answer(
    query: str,
    chunks: list[dict],
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> str:
    """Generate a grounded answer to query, using only the given chunks as context.

    Workshop Module 4 covers the anti-hallucination prompting strategy this
    should follow - the model should say it doesn't know rather than
    answer from outside the given chunks.

    model_name/temperature/max_tokens come straight from RagQueryRequest
    (models/rag.py) - None for model_name means "use whatever
    get_client_gateway().openai_chat() is already configured for", the same
    None-means-default convention vector_db already uses.
    """
    raise NotImplementedError(
        "generate_answer() is not implemented yet - see "
        "ai/rag_pipeline/response_generation/. The chat client already "
        "works: get_client_gateway().openai_chat().ask(question, context=..., "
        "temperature=..., max_tokens=...) - model_name would need a new "
        "constructor argument on OpenAIChatClient to override OPENAI_CHAT_MODEL "
        "per call, matching how IndexRequest.embedding_model already overrides "
        "OPENAI_EMBED_MODEL per call in models/documents.py."
    )


async def answer_query(
    query: str,
    top_k: int = 5,
    vector_db: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Run the full pipeline for one question: decompose, retrieve, generate.

    Called by POST /rag/query. Exceptions are deliberately not caught here -
    the router catches them and turns a NotImplementedError (today) or a
    real failure (once this is implemented) into a clear error response,
    rather than a silent or malformed one.
    """
    resolved_vector_db = vector_db or read_setting(None, "RAG_VECTOR_DB", "chromadb")

    logger.info("Answering query %r (top_k=%s, vector_db=%s)", query, top_k, resolved_vector_db)

    sub_queries = decompose_query(query)
    chunks = retrieve_chunks(sub_queries, top_k=top_k, vector_db=resolved_vector_db)
    answer = generate_answer(
        query, chunks, model_name=model_name, temperature=temperature, max_tokens=max_tokens
    )

    logger.info("Query %r answered using %d chunk(s)", query, len(chunks))

    return {"query": query, "answer": answer, "sources": chunks, "vector_db": resolved_vector_db}
