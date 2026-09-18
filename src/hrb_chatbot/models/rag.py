"""Request/response contracts for the RAG query API."""

from pydantic import BaseModel, ConfigDict, Field

from src.hrb_chatbot.common.enums import LlmProvider, SearchStrategy, VectorDB


class RagQueryRequest(BaseModel):

    model_config = ConfigDict(protected_namespaces=())

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "The question to ask the knowledge base. 2000 characters is generous for a real "
            "question (this policy document's longest single paragraph is nowhere near that) - "
            "the bound exists to reject obviously-wrong input (an empty string on one end, an "
            "entire pasted document on the other) before it ever reaches an embedding or chat "
            "completion call, not to constrain a genuine question."
        ),
    )
    top_k: int = Field(5, ge=1, le=20, description="How many chunks to retrieve and consider.")
    vector_db: VectorDB | None = Field(None, description="Override ACTIVE_VECTOR_DB for this call.")
    search_strategy: SearchStrategy | None = Field(
        None,
        description=(
            "Which retrieval technique to use - 'similarity' is the default when omitted. 'mmr' "
            "(max marginal relevance) trades some relevance for more diverse, less redundant results."
        ),
    )
    model_name: str | None = Field(
        None,
        max_length=100,
        description=(
            "Override the LLM model used to generate the answer, e.g. 'gpt-4.1-mini' or "
            "'claude-haiku-4-5'. Defaults to whichever provider/model .env is configured for "
            "(OPENAI_CHAT_MODEL by default) when left out."
        ),
    )
    temperature: float = Field(
        0.0,
        ge=0.0,
        le=2.0,
        description=(
            "How much randomness the model uses when generating the answer. 0.0 (the default) "
            "is deterministic and repeatable - the right choice for grounded HR-policy answers, "
            "where the same question should get the same answer every time. Higher values trade "
            "that repeatability for more varied wording."
        ),
    )
    max_tokens: int | None = Field(
        None,
        ge=1,
        description=(
            "Upper limit on how many tokens the generated answer may use. Left out (null), the "
            "provider's own default applies - this only needs to be set to force a shorter or "
            "longer answer than that default."
        ),
    )
    use_multi_query: bool = Field(
        False,
        description=(
            "Rewrite the question into several phrasings, search with each, and merge the results - "
            "catches relevant chunks a single phrasing misses. A layer on top of search_strategy "
            "(similarity or MMR), not a third alternative to it."
        ),
    )
    use_self_query: bool = Field(
        False,
        description=(
            "Let an LLM parse the question itself into a structured metadata filter (doc_type/"
            "department/doc_classification - see models/documents.py's DocumentRecord) before "
            "searching, e.g. 'what's my 401k vesting schedule' -> doc_classification='401k'. Falls "
            "back to an unfiltered search if parsing finds nothing or fails - see "
            "RagQueryResponse.applied_filter for what was actually parsed."
        ),
    )
    llm_provider: LlmProvider | None = Field(
        None,
        description=(
            "Which provider's model powers use_multi_query's rewriting and use_self_query's filter-"
            "parsing - 'openai' is the default when omitted. Independent of model_name/the final "
            "answer's model, which is always OpenAI today (see docs/FAQ.md)."
        ),
    )


class RetrievedChunk(BaseModel):
    """One chunk the retrieval step considered relevant to the query."""

    document_id: str = Field(..., description="Which uploaded document this chunk came from.")
    filename: str = Field(
        ..., description="That document's original filename - a citation should show this, not the "
        "opaque document_id. Looked up from the metadata store at retrieval time."
    )
    chunk_index: int = Field(..., description="This chunk's position within that document.")
    text: str = Field(..., description="The chunk's text, as stored at index time.")
    score: float | None = Field(
        None,
        description=(
            "The vector store's own similarity score for this chunk. Not "
            "comparable across backends - see pinecone_client.py's docstring "
            "on the score/distance inversion between ChromaDB and Pinecone. "
            "Null for MMR results - LangChain's max_marginal_relevance_search() "
            "does not return a per-chunk score at all."
        ),
    )


class RagQueryResponse(BaseModel):
    """What POST /rag/query returns."""

    model_config = ConfigDict(protected_namespaces=())

    query: str = Field(..., description="The question that was asked.")
    answer: str = Field(..., description="The generated, grounded answer.")
    model_used: str = Field(
        ..., description="Which chat model actually generated this answer - resolved, not just the "
        "possibly-null model_name override that was requested."
    )
    sources: list[RetrievedChunk] = Field(
        ..., description="The chunks the answer was actually grounded in, most relevant first."
    )
    vector_db: str = Field(..., description="Which vector store this query actually ran against.")
    search_strategy: str = Field(..., description="Which retrieval technique actually ran: 'similarity' or 'mmr'.")
    applied_filter: dict | None = Field(
        None,
        description=(
            "The metadata filter Self-Query actually parsed out of the question (see "
            "use_self_query), or null if use_self_query was off, found nothing to filter on, or "
            "parsing failed. Never includes is_current - that filter is always applied internally "
            "and is not something a parsed filter can see or override."
        ),
    )
