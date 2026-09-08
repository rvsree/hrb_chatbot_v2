"""ChromaDB client - the vector store this project indexes into.

Two modes, chosen by CHROMA_DB_MODE
------------------------------------
"persistent" (the default): an embedded database that writes to a local
folder (CHROMA_DB_PERSIST_DIR) - no server process to run, matches this
project's local-dev-first priority.
"http": talks to a separately-running Chroma server at CHROMA_DB_HOST:
CHROMA_DB_PORT - for when the store needs to live outside this process
(shared across processes, or run in its own container later).

Why the client is built lazily, not in __init__
-------------------------------------------------
Every other client in this project treats health_check(deep=False) as
free and instant - no network, no disk I/O beyond reading .env. In "http"
mode, constructing chromadb's HttpClient can perform a handshake against the
server, which would break that contract if it happened eagerly in __init__.
So the real client is only built the first time a method actually needs it
(get_client()), the same shape as OpenAIChatClient only building its client
when there is a key to build it with - just for a different reason here.

Collection names are sanitized
-------------------------------
ChromaDB requires collection names to be 3-512 characters, only
[a-zA-Z0-9._-], and to start/end with an alphanumeric character. A name that
violates this doesn't fail with a clear message - so it's sanitized here once,
rather than becoming a confusing error at the exact moment a document is
first indexed.
"""

import re

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("chroma_client")

_INVALID_COLLECTION_CHARACTERS = re.compile(r"[^a-zA-Z0-9._-]")


class ChromaDBClient(BaseVectorDBClient):
    """Talks to ChromaDB, embedded (persistent) or over HTTP to a Chroma server."""

    PROVIDER_NAME = "chromadb"
    ENV_KEY = "CHROMA_DB_PERSIST_DIR"

    DEFAULT_MODE = "persistent"
    DEFAULT_PERSIST_DIR = "data/chroma_db"
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 8000
    DEFAULT_COLLECTION = "hrb_chatbot_kb"

    def __init__(
        self,
        mode: str | None = None,
        persist_dir: str | None = None,
        host: str | None = None,
        port: int | None = None,
        allow_reset: str | None = None,
        collection_name: str | None = None,
    ):
        """Read settings, but do not connect to anything yet - see module docstring."""
        self.mode = read_setting(mode, "CHROMA_DB_MODE", self.DEFAULT_MODE)
        self.persist_dir = read_setting(persist_dir, "CHROMA_DB_PERSIST_DIR", self.DEFAULT_PERSIST_DIR)
        self.host = read_setting(host, "CHROMA_DB_HOST", self.DEFAULT_HOST)
        self.port = int(read_setting(port, "CHROMA_DB_PORT", self.DEFAULT_PORT))

        allow_reset_setting = read_setting(allow_reset, "CHROMA_DB_ALLOW_RESET", "false")
        self.allow_reset = str(allow_reset_setting).strip().lower() in ("1", "true", "yes")

        self.default_collection_name = read_setting(
            collection_name, "CHROMA_DB_COLLECTION", self.DEFAULT_COLLECTION
        )

        self._client = None

    def get_client(self):
        """Return the Chroma client object, building it on first use."""
        if self._client is None:
            settings = ChromaSettings(allow_reset=self.allow_reset, anonymized_telemetry=False)

            if self.mode == "http":
                logger.info("[CHROMADB] connecting over HTTP to %s:%s", self.host, self.port)
                self._client = chromadb.HttpClient(host=self.host, port=self.port, settings=settings)
            else:
                logger.info("[CHROMADB] using embedded persistent storage at %s", self.persist_dir)
                self._client = chromadb.PersistentClient(path=self.persist_dir, settings=settings)

        return self._client

    def get_configuration(self) -> dict:
        """Return the settings this client is using - nothing here is a secret."""
        config = {"mode": self.mode, "collection": self.default_collection_name}
        if self.mode == "http":
            config["host"] = self.host
            config["port"] = self.port
        else:
            config["persist_dir"] = self.persist_dir
        return config

    @staticmethod
    def sanitize_collection_name(name: str) -> str:
        """Force a name to meet ChromaDB's rules: 3-512 chars, [a-zA-Z0-9._-], alphanumeric ends."""
        sanitized = _INVALID_COLLECTION_CHARACTERS.sub("_", name).strip("_").lower()

        if len(sanitized) < 3:
            sanitized = (sanitized + "___")[:3]

        return sanitized[:512]

    def get_collection(self, collection_name: str | None = None):
        """Return one collection, creating it on first use if it doesn't exist yet."""
        name = self.sanitize_collection_name(collection_name or self.default_collection_name)
        return self.get_client().get_or_create_collection(name=name)

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        collection = self.get_collection(collection_name)
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> dict:
        collection = self.get_collection(collection_name)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def delete(self, collection_name: str, ids: list[str]) -> None:
        collection = self.get_collection(collection_name)
        collection.delete(ids=ids)

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only reports the settings in use - no client is built, so
        "http" mode makes no network call here.
        deep=True: builds the client and calls list_collections(), which for
        "http" mode is also the first real proof the server is reachable.
        """
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not deep:
            result["status"] = "configured"
            return result

        try:
            collections = self.get_client().list_collections()
            result["status"] = "healthy"
            result["collections_visible"] = len(collections)
        except Exception as error:
            # A health check must never crash - report the problem instead.
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
