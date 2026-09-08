"""One place that hands out every database client the project uses.

Same reasoning as common/clients/llm_client/client_gateway.py: without this,
every module that needed the vector store would build its own ChromaDBClient,
reading the same settings over and over. See that file for the fuller
explanation - this is the same pattern, one layer over for databases.
"""

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient
from src.hrb_chatbot.common.clients.db_client.chroma_client import ChromaDBClient
from src.hrb_chatbot.common.clients.db_client.pinecone_client import PineconeClient
from src.hrb_chatbot.common.clients.db_client.postgres_client import PostgresClient
from src.hrb_chatbot.common.clients.db_client.sqlite_client import SQLiteClient
from src.hrb_chatbot.common.config.settings import read_setting


class DBGateway:
    """Creates each database client once, then returns that same client every time."""

    def __init__(self):
        self.chroma_client = None
        self.pinecone_client = None
        self.sqlite_client = None
        self.postgres_client = None

    def chroma(self) -> ChromaDBClient:
        """Return the shared ChromaDB client, building it on first use."""
        if self.chroma_client is None:
            self.chroma_client = ChromaDBClient()
        return self.chroma_client

    def pinecone(self) -> PineconeClient:
        """Return the shared Pinecone client, building it on first use."""
        if self.pinecone_client is None:
            self.pinecone_client = PineconeClient()
        return self.pinecone_client

    def vector_store(self, provider: str | None = None) -> BaseVectorDBClient:
        """Return whichever vector store is selected.

        This is the accessor ai/doc_processing/indexing and
        ai/rag_pipeline/query_retrieval should call - never chroma() or
        pinecone() directly - so switching the active backend is a one-line
        .env change, not a code change in every caller.

        Pass `provider` to override RAG_VECTOR_DB for one call - this is
        what lets POST /rag/documents/{id}/index accept vector_db in its
        request body per-call, not just as a global .env default.

        Raises ValueError on an unrecognized name, either from .env or from
        a caller, rather than silently falling back to ChromaDB - a typo
        here (RAG_VECTOR_DB=chromdb) is exactly the kind of mistake that
        should fail loudly, not quietly index into the wrong store.
        """
        provider = provider or read_setting(None, "RAG_VECTOR_DB", "chromadb")

        if provider == "chromadb":
            return self.chroma()
        if provider == "pinecone":
            return self.pinecone()

        raise ValueError(f"Unknown vector store {provider!r} - use 'chromadb' or 'pinecone'")

    def sqlite(self) -> SQLiteClient:
        """Return the shared SQLite client, building it on first use."""
        if self.sqlite_client is None:
            self.sqlite_client = SQLiteClient()
        return self.sqlite_client

    def postgres(self) -> PostgresClient:
        """Return the shared Postgres client, building it on first use."""
        if self.postgres_client is None:
            self.postgres_client = PostgresClient()
        return self.postgres_client

    def metadata_store(self, provider: str | None = None) -> BaseMetadataClient:
        """Return whichever document-metadata store is selected.

        This is the accessor documents_service.py and
        ai/doc_processing/indexing should call - never sqlite() or
        postgres() directly - matching vector_store()'s reasoning below.

        'sqlite' writes to local disk, which does not survive a restart or
        redeploy on a platform with no persistent volume (App Runner,
        Lambda) - see docs/S3-ASYNC-UPLOAD-DESIGN.md. 'postgres' is meant
        for exactly that case: point POSTGRES_DB_HOST/PORT/NAME/USER/PASSWORD
        at any reachable Postgres - a local dev server or a hosted one like
        Neon - PostgresClient does not care which.

        Raises ValueError on an unrecognized name, same reasoning as
        vector_store() - a typo here should fail loudly, not silently keep
        writing to a store the deployment can't actually persist.
        """
        provider = provider or read_setting(None, "RAG_METADATA_STORE", "sqlite")

        if provider == "sqlite":
            return self.sqlite()
        if provider == "postgres":
            return self.postgres()

        raise ValueError(f"Unknown metadata store {provider!r} - use 'sqlite' or 'postgres'")


# The single gateway shared by the whole program - same convention as
# client_gateway.py's _shared_gateway.
_shared_db_gateway = None


def get_db_gateway() -> DBGateway:
    """Return the one shared DBGateway, creating it on the first call."""
    global _shared_db_gateway

    if _shared_db_gateway is None:
        _shared_db_gateway = DBGateway()

    return _shared_db_gateway


def reset_db_gateway():
    """Throw away the shared gateway so the next call builds a fresh one.

    Only needed in tests: a client reads its settings once, when it is built,
    so a test that changes an environment variable must clear the cache for
    the change to have any effect.
    """
    global _shared_db_gateway
    _shared_db_gateway = None
