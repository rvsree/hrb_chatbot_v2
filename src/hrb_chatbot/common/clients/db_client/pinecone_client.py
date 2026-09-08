"""Pinecone client - an alternative vector store to ChromaDB.

Same BaseVectorDBClient contract as chroma_client.py - the two are
interchangeable behind db_gateway.py. ChromaDB is the active store today;
this is real and tested on its own, so switching later is a config change
plus a gateway call, matching how postgres_client.py relates to
sqlite_client.py for document metadata.

One index, namespaces instead of collections
------------------------------------------------
Pinecone's unit of isolation within one index is a "namespace", not a
separately-dimensioned "collection" the way Chroma has - a single index has
one fixed vector dimension for everything in it. So `collection_name` in
every method below is passed straight through as the Pinecone namespace.
One PINECONE_INDEX_NAME is configured for this whole client; if this project
ever needs genuinely different embedding dimensions side by side, that
needs a second index (and a second client instance), not a new namespace.

Pinecone has no native "documents" field like Chroma
---------------------------------------------------------
A Pinecone vector is just an id, its values (the embedding), and a metadata
dict. To keep parity with Chroma - where `query()` hands back the original
chunk text, not just an id - the raw text is stored under a `"document"`
metadata key on upsert, and pulled back out of `match.metadata["document"]`
on query.

The score/distance inversion - read this before writing retrieval code
---------------------------------------------------------------------------
Chroma's `query()` returns "distances": lower means more similar. Pinecone's
`query()` returns "score": for the cosine metric this project uses, HIGHER
means more similar - it is a similarity, not a distance. This method still
returns the field under the key "distances" for shape-compatibility with
ChromaDBClient, but the *number itself means the opposite thing* depending
on which client answered. This is not silently corrected here (a
1-minus-score transform is only valid for one specific metric convention,
and guessing wrong would be worse than leaving it visible) - whatever reads
this field to rank or filter results must know which backend produced it.

Index creation happens lazily, on first real use
-----------------------------------------------------
Same reasoning as every other client here: health_check(deep=False) must
stay instant. Creating a serverless index for real (deep=True, or the first
upsert/query/delete) is not instant - Pinecone takes a few seconds to make a
freshly created index ready, so _ensure_index() polls briefly rather than
assuming it's ready the moment create_index() returns.
"""

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
        """Read settings and build the lightweight Pinecone client object.

        Building `Pinecone(api_key=...)` makes no network call by itself -
        it is safe to do here rather than lazily, the same as OpenAI()'s
        constructor. Creating/confirming the *index* is the part that is
        deferred - see _ensure_index().
        """
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
            # No metadata given - one empty dict per id, so the loop below
            # always has something to merge into, even if it's nothing.
            metadatas = []
            for _ in ids:
                metadatas.append({})

        # Build one Pinecone vector record per chunk. ids, embeddings,
        # documents, and metadatas are four separate parallel lists - the
        # item at index 0 of each belongs together, the item at index 1 of
        # each belongs together, and so on - so this loop walks all four at
        # the same time using Python's zip(), which pairs up corresponding
        # items the way iterating four Java arrays with one shared index
        # variable would. strict=True makes zip() raise an error instead of
        # silently truncating if the four lists ever end up different
        # lengths, which would otherwise be a confusing bug to track down.
        vectors = []
        for id_, embedding, document, metadata in zip(ids, embeddings, documents, metadatas, strict=True):
            # Pinecone has no native "document text" field - store it as
            # metadata like any other value, alongside whatever the caller
            # already put in `metadata` (document_id, chunk_index).
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
            documents.append(metadata.pop("document", ""))
            metadatas.append(metadata)
            scores.append(match.score)

        # Nested once, matching Chroma's shape for a single query embedding.
        # "distances" here are Pinecone similarity SCORES (higher = closer for
        # cosine) - see this module's docstring before ranking on this field.
        return {"ids": [ids], "documents": [documents], "metadatas": [metadatas], "distances": [scores]}

    def delete(self, collection_name: str, ids: list[str]) -> None:
        with log_backend_call(
            logger, "pinecone", "vector.delete", namespace=collection_name, chunk_count=len(ids)
        ):
            self.get_index().delete(ids=ids, namespace=collection_name)

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only reports configured settings - no network call.
        deep=True: lists indexes (free) and confirms/creates the configured
        one, reporting whether it already existed or was just created.
        """
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.api_key:
            result["status"] = "unhealthy"
            result["message"] = "API key not configured"
            return result

        if not deep:
            result["status"] = "configured"
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
