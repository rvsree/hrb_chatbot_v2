"""Pinecone client - an alternative vector store to ChromaDB, same BaseVectorDBClient contract.

Key gotcha: Pinecone's query() returns similarity "score" (higher = closer),
not Chroma's "distance" (lower = closer) - both are returned under the key
"distances" for shape-compatibility, but the number means the opposite thing.
"""

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
    """Temporary compatibility shim, added alongside the vector_indexer.py
    rewrite onto LlamaIndex's VectorStoreIndex (ai/doc_processing/indexing/):
    LlamaIndex's PineconeVectorStore does not write chunk text under this
    client's own "document" metadata key - the text lives inside a
    "_node_content" JSON string LlamaIndex writes for its own use instead.
    Without this, every chunk indexed the new way came back with text=""
    here - confirmed live: a real query returned correct document_id/
    filename/score for its top matches, but an empty context, and the LLM
    correctly (but unhelpfully) answered "I don't know" for a question its
    retrieved chunks actually did cover. Chroma has no equivalent gap - it
    stores chunk text natively, separate from metadata, regardless of who
    wrote it. Safe to remove once ai/rag_pipeline/query_retrieval/
    retriever.py itself is rewritten on LangChain (planned next), since that
    rewrite reads from wherever LlamaIndex actually put the text either way,
    not through this client's "document" convention at all."""
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

        # ids, embeddings, documents, and metadatas are four separate lists that
        # line up by position (index 0 of each belongs together, index 1 of each
        # belongs together...). zip() walks all four at once instead of writing
        # `for i in range(len(ids)): ids[i], embeddings[i], ...` by hand - closest
        # Java equivalent is iterating four arrays with one shared index variable.
        # strict=True raises instead of silently truncating if their lengths differ.
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
        """Pinecone's update() takes one id at a time (no batch metadata-update
        call), and merges set_metadata into the existing dict rather than
        replacing it - harmless here since callers always pass the complete
        desired metadata anyway (see BaseVectorDBClient's contract). One real
        gap: Pinecone stores chunk text under metadata["document"] (no native
        text field, unlike Chroma) - a caller that omits "document" from the
        dict it passes will lose that chunk's text on Pinecone specifically.
        Acceptable today because the only caller (flipping is_current=false on
        a superseded document) only ever affects chunks retrieval already
        excludes - not acceptable if this method gains other callers later."""
        with log_backend_call(
            logger, "pinecone", "vector.update_metadata", namespace=collection_name, chunk_count=len(ids)
        ):
            index = self.get_index()
            for id_, metadata in zip(ids, metadatas, strict=True):
                index.update(id=id_, set_metadata=metadata, namespace=collection_name)

    def health_check(self) -> dict:
        """Report whether this client is usable: lists indexes, then calls
        _ensure_index(), which CREATES the configured index if it doesn't exist
        yet (a one-time, billable side effect - see _ensure_index's own docstring;
        it's a no-op on every call after the first, so repeat health checks don't
        repeat it)."""
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
