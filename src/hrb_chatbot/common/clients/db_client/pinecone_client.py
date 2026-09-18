"""Pinecone client - alternative to ChromaDB, same BaseVectorDBClient contract.
Gotcha: query() returns "score" (higher=closer), not Chroma's "distance"
(lower=closer) - both come back under "distances" for shape parity."""

import json
import time

from pinecone import Pinecone, ServerlessSpec

from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("pinecone_client")

# How long to wait, total, for a freshly created index to report ready before
# giving up - serverless indexes are typically ready in a few seconds.
INDEX_READY_TIMEOUT_SECONDS = 60
INDEX_READY_POLL_SECONDS = 2


def _text_from_llama_index_node_content(metadata: dict) -> str:
    """LlamaIndex (pre-Phase 17) stored chunk text inside a "_node_content"
    JSON blob instead of this client's own "document" key - kept for
    backward compat with any such vectors still in the index."""
    raw_node_content = metadata.get("_node_content")
    if not raw_node_content:
        return ""
    try:
        return json.loads(raw_node_content).get("text", "")
    except (json.JSONDecodeError, AttributeError):
        return ""


class PineconeClient(BaseVectorDBClient):
    """Talks to Pinecone."""

    PROVIDER_NAME = "pinecone"
    ENV_KEY = "PINECONE_API_KEY"

    DEFAULT_CLOUD = "aws"
    DEFAULT_REGION = "us-east-1"
    DEFAULT_METRIC = "cosine"
    DEFAULT_DIMENSION = 1536

    def __init__(
        self,
        api_key: str | None = None,
        index_name: str | None = None,
        cloud: str | None = None,
        region: str | None = None,
        metric: str | None = None,
        dimension: int | None = None,
    ):
        """Read settings and build the lightweight Pinecone client object - this
        makes no network call by itself; creating/confirming the index is deferred, see _ensure_index()."""
        self.api_key = read_setting(api_key, "PINECONE_API_KEY")
        self.index_name = read_setting(index_name, "PINECONE_INDEX_NAME")
        self.cloud = read_setting(cloud, "PINECONE_CLOUD", self.DEFAULT_CLOUD)
        self.region = read_setting(region, "PINECONE_ENVIRONMENT", self.DEFAULT_REGION)
        self.metric = read_setting(metric, "PINECONE_METRIC", self.DEFAULT_METRIC)
        self.dimension = int(read_setting(dimension, "PINECONE_DIMENSION", self.DEFAULT_DIMENSION))

        if not self.api_key:
            logger.warning("[PINECONE] PINECONE_API_KEY not set")

        if self.api_key:
            self._client = Pinecone(api_key=self.api_key)
        else:
            self._client = None
        self._index = None
        self._index_ready = False

    def get_configuration(self) -> dict:
        """Return the settings this client is using - nothing here is a secret."""
        return {
            "index_name": self.index_name,
            "cloud": self.cloud,
            "region": self.region,
            "metric": self.metric,
            "dimension": self.dimension,
        }

    def _require_client(self) -> Pinecone:
        if self._client is None:
            raise RuntimeError("PINECONE_API_KEY is not configured")
        return self._client

    def _ensure_index(self) -> None:
        """Create the configured index if it doesn't exist yet, and wait for it
        to report ready. Safe to call repeatedly - a no-op once ready."""
        if self._index_ready:
            return

        client = self._require_client()

        if not client.has_index(self.index_name):
            logger.info(
                "[PINECONE] creating serverless index %r (dimension=%s, metric=%s, %s/%s)",
                self.index_name,
                self.dimension,
                self.metric,
                self.cloud,
                self.region,
            )
            client.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )

        waited = 0
        while not client.describe_index(self.index_name).status["ready"]:
            if waited >= INDEX_READY_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Pinecone index {self.index_name!r} did not become ready within "
                    f"{INDEX_READY_TIMEOUT_SECONDS}s"
                )
            time.sleep(INDEX_READY_POLL_SECONDS)
            waited += INDEX_READY_POLL_SECONDS

        self._index_ready = True

    def get_index(self):
        """Return the Index handle, ensuring the index exists and is ready first."""
        self._ensure_index()

        if self._index is None:
            self._index = self._require_client().Index(self.index_name)

        return self._index

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        if metadatas is None:
            # No metadata given - fill in an empty dict per id so the merge loop below
            # always has something to write into.
            metadatas = []
            for _ in ids:
                metadatas.append({})

        # Four lists line up by position - zip() walks all at once (Java:
        # iterating four arrays with one shared index). strict=True catches
        # mismatched lengths instead of silently truncating.
        vectors = []
        for id_, embedding, document, metadata in zip(ids, embeddings, documents, metadatas, strict=True):
            # Pinecone has no native "document text" field - stash it in metadata
            # alongside whatever the caller already put there (document_id, chunk_index).
            vector_metadata = dict(metadata)
            vector_metadata["document"] = document
            vectors.append({"id": id_, "values": embedding, "metadata": vector_metadata})

        with log_backend_call(
            logger, "pinecone", "vector.upsert", namespace=collection_name, chunk_count=len(vectors)
        ):
            self.get_index().upsert(vectors=vectors, namespace=collection_name)

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> dict:
        with log_backend_call(logger, "pinecone", "vector.query", namespace=collection_name, top_k=top_k):
            response = self.get_index().query(
                vector=query_embedding,
                top_k=top_k,
                namespace=collection_name,
                filter=where,
                include_metadata=True,
            )

        ids, documents, metadatas, scores = [], [], [], []
        for match in response.matches:
            metadata = dict(match.metadata or {})
            ids.append(match.id)
            documents.append(metadata.pop("document", "") or _text_from_llama_index_node_content(metadata))
            metadatas.append(metadata)
            scores.append(match.score)

        # Nested once to match Chroma's shape. "distances" here are Pinecone
        # similarity scores (higher = closer) - see module docstring.
        return {"ids": [ids], "documents": [documents], "metadatas": [metadatas], "distances": [scores]}

    def delete(self, collection_name: str, ids: list[str]) -> None:
        with log_backend_call(
            logger, "pinecone", "vector.delete", namespace=collection_name, chunk_count=len(ids)
        ):
            self.get_index().delete(ids=ids, namespace=collection_name)

    def update_metadata(self, collection_name: str, ids: list[str], metadatas: list[dict]) -> None:
        """Pinecone's update() is per-id and merges set_metadata rather than
        replacing - harmless only because every caller here already passes
        the full desired metadata. Gap: omitting "document" loses that chunk's text."""
        with log_backend_call(
            logger, "pinecone", "vector.update_metadata", namespace=collection_name, chunk_count=len(ids)
        ):
            index = self.get_index()
            for id_, metadata in zip(ids, metadatas, strict=True):
                index.update(id=id_, set_metadata=metadata, namespace=collection_name)

    def health_check(self) -> dict:
        """Lists indexes, then calls _ensure_index() - creates the index on
        first call (billable), a no-op after."""
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.api_key:
            result["status"] = "unhealthy"
            result["message"] = "API key not configured"
            return result

        try:
            client = self._require_client()
            existing_indexes = [index["name"] for index in client.list_indexes()]
            index_already_existed = self.index_name in existing_indexes

            self._ensure_index()
            stats = self.get_index().describe_index_stats()

            result["status"] = "healthy"
            result["indexes_visible"] = len(existing_indexes)
            result["index_already_existed"] = index_already_existed
            result["total_vector_count"] = stats.get("total_vector_count", 0)
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
