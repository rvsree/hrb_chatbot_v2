"""Fixed value sets for "which backend" fields, as StrEnum (like a Java enum)
- FastAPI rejects an unknown value with a 422 at the boundary, and each
member compares/serializes as its plain string, no `.value` needed."""

from enum import StrEnum


class VectorDB(StrEnum):
    """Which vector store holds document chunks - see db_gateway.DBGateway.vector_store()."""

    CHROMADB = "chromadb"
    PINECONE = "pinecone"


class MetadataStore(StrEnum):
    """Which store holds one row per uploaded document - see db_gateway.DBGateway.metadata_store()."""

    SQLITE = "sqlite"
    POSTGRES = "postgres"


class LlmProvider(StrEnum):
    """Which chat LLM provider to use - see client_gateway.ClientGateway."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    BEDROCK = "bedrock"


class ChunkingStrategy(StrEnum):
    """How to split text into chunks - see text_chunker.CHUNKING_STRATEGIES
    (must keep matching) and decide_chunking_strategy()'s auto-selected default."""

    FIXED = "fixed"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    MARKDOWN = "markdown"
    HTML = "html"
    NONE = "none"


class SearchStrategy(StrEnum):
    """Which retrieval technique to run a query with - see
    retriever.SEARCH_STRATEGIES (the dict these values must keep matching)."""

    SIMILARITY = "similarity"
    MMR = "mmr"


class Role(StrEnum):
    """Who's calling the API, for the gateway's role-based access check -
    see api/gateway/rbac.py. HR_SUPPORT uploads documents; all three can retrieve."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR_SUPPORT = "hr_support"
