"""The fixed, small sets of valid values for "which backend do you want" fields.

Before this module existed, a field like `vector_db` was just a `str`, and every
layer that cared re-typed the same two or three valid values by hand: once in a
Field(description=...), again as the hardcoded default ("chromadb") in three or
four different function signatures, and again in an if/elif chain that checked it.
A typo in any of those places either silently fell through to a default (unnoticed)
or only blew up deep in the call stack, well after the request had already started
doing real work.

A Python Enum fixes both problems, the same way a Java enum does: FastAPI rejects
an unknown value with a clear 422 right at the API boundary, before any work starts,
and the accepted values live in exactly one place - here - instead of being retyped
everywhere they're used.

These all subclass `str` (via `StrEnum`), so a member such as `VectorDB.CHROMADB`
can be compared to, and JSON-serialized as, the plain string "chromadb" - no extra
`.value` unwrapping needed at most call sites.
"""

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
