"""Plain, framework-free container for one /query request - kept out of
every layer's signature. Not Pydantic: only routes/ owns request models
(see CLAUDE.md's architecture section)."""

from dataclasses import dataclass


@dataclass
class RagQueryParams:
    query: str
    top_k: int = 5
    vector_db: str | None = None
    search_strategy: str | None = None
    model_name: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    use_multi_query: bool = False
    use_self_query: bool = False
    llm_provider: str | None = None
