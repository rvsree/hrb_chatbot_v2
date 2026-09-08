"""Request/response contracts for the RAG query API."""

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    """What POST /rag/query accepts."""

    query: str = Field(..., min_length=1, description="The question to ask the knowledge base.")
    top_k: int = Field(5, ge=1, le=20, description="How many chunks to retrieve and consider.")
    vector_db: str | None = Field(
        None, description="Override RAG_VECTOR_DB for this call: 'chromadb' or 'pinecone'."
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
