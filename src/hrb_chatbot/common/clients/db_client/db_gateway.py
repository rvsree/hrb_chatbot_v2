"""One place that hands out every database client the project uses."""

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient
from src.hrb_chatbot.common.clients.db_client.chroma_client import ChromaDBClient
from src.hrb_chatbot.common.clients.db_client.pinecone_client import PineconeClient
from src.hrb_chatbot.common.clients.db_client.postgres_client import PostgresClient
from src.hrb_chatbot.common.clients.db_client.sqlite_client import SQLiteClient
from src.hrb_chatbot.common.config.settings import get_active_vector_db, read_setting
from src.hrb_chatbot.common.enums import MetadataStore, VectorDB


class DBGateway:
   # Creates each database client once, then returns that same client every time.

    def __init__(self):
        self.chroma_client = None
        self.pinecone_client = None
        self.sqlite_client = None
        self.postgres_client = None

    def chroma(self) -> ChromaDBClient:
        # Return the shared ChromaDB client, building it on first use.
        if self.chroma_client is None:
            self.chroma_client = ChromaDBClient()
        return self.chroma_client

    def pinecone(self) -> PineconeClient:
        # Return the shared Pinecone client, building it on first use.
        if self.pinecone_client is None:
            self.pinecone_client = PineconeClient()
        return self.pinecone_client

    def vector_store(self, provider: str | None = None) -> BaseVectorDBClient:
        """Return whichever vector store is selected."""
        provider = get_active_vector_db(provider)

        if provider == VectorDB.CHROMADB:
            return self.chroma()
        if provider == VectorDB.PINECONE:
            return self.pinecone()

        raise ValueError(f"Unknown vector store {provider!r} - use one of {[member.value for member in VectorDB]}")

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
        # Return whichever document-metadata store is selected.
        provider = provider or read_setting(None, "RAG_METADATA_STORE", MetadataStore.SQLITE)

        if provider == MetadataStore.SQLITE:
            return self.sqlite()
        if provider == MetadataStore.POSTGRES:
            return self.postgres()

        raise ValueError(
            f"Unknown metadata store {provider!r} - use one of {[member.value for member in MetadataStore]}"
        )


# The single gateway shared by the whole program - same convention as client_gateway.py's _shared_gateway.
_shared_db_gateway = None


def get_db_gateway() -> DBGateway:
    # Return the one shared DBGateway, creating it on the first call.
    global _shared_db_gateway

    if _shared_db_gateway is None:
        _shared_db_gateway = DBGateway()

    return _shared_db_gateway


def reset_db_gateway():
    global _shared_db_gateway
    _shared_db_gateway = None
