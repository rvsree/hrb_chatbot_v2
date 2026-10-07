"""Request/response contracts for the RAG query API - see docs/agent-reference/endpoint-request-response-contracts.md."""

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
        "(doc_category/department/doc_description) before searching.",
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
    enable_conversation_memory: bool = Field(
        False, description="Carry conversation history across calls, server-side, keyed by conversation_id."
    )
    conversation_id: str | None = Field(
        None,
        description="Pass back the value from a prior response to continue that conversation. Ignored if "
        "enable_conversation_memory is false; a new one is generated if true and this is omitted.",
    )


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


class LatencyInfo(BaseModel):
    total: float = Field(..., description="Total wall-clock time for this call, in milliseconds.")
    retrieval: float | None = Field(None, description="Time spent retrieving chunks, in milliseconds. Null on a cache hit.")
    generation: float | None = Field(None, description="Time spent generating the answer, in milliseconds. Null on a cache hit.")
    eval: float | None = Field(None, description="Time spent on live eval-judge scoring, in milliseconds. Null when no eval ran this call (cache hit, MCP, or no context).")


class TokenUsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class EvalScores(BaseModel):
    """Phase 109 - live LLM-as-judge scores, same prompts/parsing as the
    offline golden-dataset harness (golden_dataset_harness.py), run
    synchronously per live response at the user's explicit request
    (accepted tradeoff: 2 extra judge LLM calls per live - not cached -
    generation). 0.0-1.0, not 0-10 - already normalized by the judge."""

    groundedness: float = Field(..., description="Is the answer supported by the retrieved context? 0.0-1.0.")
    groundedness_verdict: str = Field(..., description="GROUNDED (>=0.7), PARTIAL (>=0.4), or HALLUCINATED.")
    completeness: float = Field(..., description="Does the answer fully address the question? 0.0-1.0.")
    completeness_verdict: str = Field(..., description="COMPLETE (>=0.7), PARTIAL (>=0.4), or INCOMPLETE.")


class ExplainabilityInfo(BaseModel):
    """Phase 107/109 - real latency/token/cache-vs-live/eval numbers,
    genai-rag only. Dollar cost is deliberately excluded (see BACKLOG.md)."""

    served_from_cache: bool = Field(..., description="True if this answer came from the answer cache, not a live retrieval+generation call.")
    llm_call_count: int = Field(..., description="How many LLM calls this request made - 0 on a cache hit or MCP fast-path, 1 otherwise. Excludes eval-judge calls.")
    latency_ms: LatencyInfo
    token_usage: TokenUsageInfo | None = Field(None, description="Null on a cache hit, MCP fast-path, or a no-context answer that never called the LLM.")
    routed_to: str | None = Field(None, description="The MCP tool name if this answer was dynamically routed there instead of RAG (Phase 49/108). Null otherwise.")
    eval_scores: EvalScores | None = Field(None, description="Null for an MCP answer or a no-context answer (nothing to check groundedness against). Reused as-is on a cache hit - same answer, same score, not re-judged.")


class RagQueryResponse(BaseModel):
    """What POST /query returns."""

    query: str = Field(..., description="The question that was asked.")
    answer_info: AnswerInfo
    retrieval_info: RetrievalInfo
    explainability_info: ExplainabilityInfo
    conversation_id: str | None = Field(
        None,
        description="Echoed/generated when enable_conversation_memory was true - pass it back on the next "
        "call to continue this conversation. Null when memory wasn't enabled.",
    )
