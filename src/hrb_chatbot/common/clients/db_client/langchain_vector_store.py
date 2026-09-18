"""Wraps this project's own ChromaDB/Pinecone clients into LangChain's own
VectorStore objects - the one shared builder for both query and write sides."""

import json

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting

# The one collection/namespace every provider writes into and reads from -
# shared so a typo in one place can't silently create a second collection.
COLLECTION_NAME = "hrb_chatbot_kb"


class _TextBackfillPineconeIndex:
    """Backfills a "text" metadata key on query results from whichever of two
    older storage shapes a chunk actually used, so LangChain's unguarded
    metadata.pop("text") never raises - see docs/FAQ.md's entry 8."""

    def __init__(self, real_index):
        self._real_index = real_index

    def __getattr__(self, name):
        return getattr(self._real_index, name)

    def query(self, *args, **kwargs):
        response = self._real_index.query(*args, **kwargs)
        for match in response.matches:
            if not match.metadata or "text" in match.metadata:
                continue
            match.metadata["text"] = self._extract_text(match.metadata)
        return response

    @staticmethod
    def _extract_text(metadata: dict) -> str:
        if "_node_content" in metadata:
            try:
                return json.loads(metadata["_node_content"]).get("text", "")
            except (json.JSONDecodeError, AttributeError):
                return ""
        if "document" in metadata:
            return metadata["document"]
        return ""


def get_embeddings(embedding_model: str | None = None) -> OpenAIEmbeddings:
    api_key = read_setting(None, "OPENAI_API_KEY")
    base_url = read_url_setting(None, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    resolved_model = read_setting(embedding_model, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
    return OpenAIEmbeddings(api_key=api_key, base_url=base_url, model=resolved_model)


def get_vector_store(
    vector_db: str | None, embedding_model: str | None = None, collection_name: str = COLLECTION_NAME
):
    """Return (LangChain vector store, resolved provider name). collection_name
    is a real parameter, not just the module constant, so a test can point at
    an isolated collection without monkeypatching a global."""
    vector_store_client = get_db_gateway().vector_store(provider=vector_db)
    embeddings = get_embeddings(embedding_model)

    if vector_store_client.PROVIDER_NAME == "pinecone":
        wrapped_index = _TextBackfillPineconeIndex(vector_store_client.get_index())
        store = PineconeVectorStore(index=wrapped_index, embedding=embeddings, namespace=collection_name)
    else:
        store = Chroma(
            client=vector_store_client.get_client(),
            collection_name=collection_name,
            embedding_function=embeddings,
        )

    return store, vector_store_client.PROVIDER_NAME
