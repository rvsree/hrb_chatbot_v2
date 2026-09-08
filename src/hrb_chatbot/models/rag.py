"""Request/response contracts for the RAG query API."""

from pydantic import BaseModel, ConfigDict, Field


class RagQueryRequest(BaseModel):
    """What POST /rag/query accepts.

    model_config below turns off Pydantic's "model_" protected-namespace
    warning specifically - Pydantic reserves fields starting with "model_"
    for its own internal use (model_config, model_fields, ...) and warns on
    any field name that collides with that prefix. model_name here is a
    genuinely different thing (which LLM model to call), not a clash worth
    renaming the field over.

    Every field below query is optional - the request body {"query": "..."}
    on its own is enough. Each optional field only overrides its one .env
    default for this one call, the same pattern IndexRequest already uses in
    models/documents.py - a caller only needs to name the values that differ
    from the default, not repeat every setting on every request.
    """

    model_config = ConfigDict(protected_namespaces=())

    query: str = Field(..., min_length=1, description="The question to ask the knowledge base.")
    top_k: int = Field(5, ge=1, le=20, description="How many chunks to retrieve and consider.")
    vector_db: str | None = Field(
        None, description="Override RAG_VECTOR_DB for this call: 'chromadb' or 'pinecone'."
    )
    model_name: str | None = Field(
        None,
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


class RetrievedChunk(BaseModel):
    """One chunk the retrieval step considered relevant to the query."""

    document_id: str = Field(..., description="Which uploaded document this chunk came from.")
    chunk_index: int = Field(..., description="This chunk's position within that document.")
    text: str = Field(..., description="The chunk's text, as stored at index time.")
    score: float = Field(
        ...,
        description=(
            "The vector store's own similarity score for this chunk. Not "
            "comparable across backends - see pinecone_client.py's docstring "
            "on the score/distance inversion between ChromaDB and Pinecone."
        ),
    )


class RagQueryResponse(BaseModel):
    """What POST /rag/query returns."""

    query: str = Field(..., description="The question that was asked.")
    answer: str = Field(..., description="The generated, grounded answer.")
    sources: list[RetrievedChunk] = Field(
        ..., description="The chunks the answer was actually grounded in, most relevant first."
    )
    vector_db: str = Field(..., description="Which vector store this query actually ran against.")
