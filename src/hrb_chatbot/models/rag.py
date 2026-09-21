"""Request/response contracts for the RAG query API (Phase 45: nested
sub-objects, identity via payload not headers - see
docs/endpoint-request-response-contracts.md, the source of truth for these shapes)."""

from pydantic import BaseModel, ConfigDict, Field

from src.hrb_chatbot.common.enums import LlmProvider, SearchStrategy, VectorDB
from src.hrb_chatbot.models.common import UserProfile


class SearchOptions(BaseModel):
    top_k: int | None = Field(
        None, ge=1, le=20, description="How many chunks to retrieve and consider - defaults to RAG_DEFAULT_TOP_K."
    )
    vector_db: VectorDB | None = Field(None, description="Override ACTIVE_VECTOR_DB for this call.")
    search_strategy: SearchStrategy | None = Field(
        None,
        description="Which retrieval technique to use - 'similarity' is the default when omitted. "
        "'mmr' trades some relevance for more diverse, less redundant results.",
    )
    use_multi_query: bool = Field(
        False,
        description="Rewrite the question into several phrasings, search with each, and merge the "
        "results - catches relevant chunks a single phrasing misses.",
    )
    use_self_query: bool = Field(
        False,
        description="Let an LLM parse the question itself into a structured metadata filter "
        "(doc_type/department/doc_classification) before searching.",
    )
    llm_provider: LlmProvider | None = Field(
        None,
        description="Which provider powers use_multi_query's rewriting and use_self_query's "
        "filter-parsing - 'openai' is the default when omitted.",
    )


class GenerationOptions(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str | None = Field(
        None,
        max_length=100,
        description="Override the LLM model used to generate the answer, e.g. 'gpt-4.1-mini'.",
    )
    temperature: float | None = Field(
        None, ge=0.0, le=2.0, description="How much randomness the model uses - defaults to RAG_DEFAULT_TEMPERATURE."
    )
    max_tokens: int | None = Field(None, ge=1, description="Upper limit on the generated answer's token count.")


class RagQueryRequest(BaseModel):
    user_profile: UserProfile | None = None
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask the knowledge base.",
    )
    search_options: SearchOptions | None = None
    generation_options: GenerationOptions | None = None


class RetrievedChunk(BaseModel):
    """One chunk the retrieval step considered relevant to the query."""

    document_id: str = Field(..., description="Which uploaded document this chunk came from.")
    filename: str = Field(..., description="That document's original filename.")
    chunk_index: int = Field(..., description="This chunk's position within that document.")
    text: str = Field(..., description="The chunk's text, as stored at index time.")
    score: float | None = Field(None, description="The vector store's own similarity score, null for MMR results.")


class AnswerInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str = Field(..., description="The generated, grounded answer.")
    model_used: str = Field(..., description="Which chat model actually generated this answer.")


class RetrievalInfo(BaseModel):
    vector_db: str = Field(..., description="Which vector store this query actually ran against.")
    search_strategy: str = Field(..., description="Which retrieval technique actually ran: 'similarity' or 'mmr'.")
    applied_filter: dict | None = Field(
        None, description="The metadata filter Self-Query actually parsed out of the question, if any."
    )
    sources: list[RetrievedChunk] = Field(..., description="The chunks the answer was actually grounded in.")


class RagQueryResponse(BaseModel):
    """What POST /query returns."""

    query: str = Field(..., description="The question that was asked.")
    answer_info: AnswerInfo
    retrieval_info: RetrievalInfo
