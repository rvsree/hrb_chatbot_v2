"""Postgres-backed embedding cache (Phase 77) - exact-match on
(content_hash, embedding_model), avoids re-embedding unchanged chunk text
on re-index. Ingestion-side only - query-time caching is a scoped
follow-up (see BACKLOG.md), not built here. Same psycopg-via-
asyncio.to_thread() pattern as postgres_client.py/conversation_store.py."""

import asyncio
import hashlib
import json

import psycopg

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("embedding_cache")

CREATE_EMBEDDING_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (content_hash, embedding_model)
)
"""


def hash_text(text: str) -> str:
    """Same hashing approach documents_service.py already uses for
    document-level content_hash, applied at chunk granularity instead."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Caches embedding vectors by content hash + model."""

    PROVIDER_NAME = "postgres"
    ENV_KEY = "POSTGRES_DB_HOST"

    DEFAULT_PORT = "5432"

    def __init__(
        self,
        host: str | None = None,
        port: str | None = None,
        db_name: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.host = read_setting(host, "POSTGRES_DB_HOST")
        self.port = read_setting(port, "POSTGRES_DB_PORT", self.DEFAULT_PORT)
        self.db_name = read_setting(db_name, "POSTGRES_DB_NAME")
        self.user = read_setting(user, "POSTGRES_DB_USER")
        self.password = read_setting(password, "POSTGRES_DB_PASSWORD")

        if not self.host:
            logger.warning("[POSTGRES] POSTGRES_DB_HOST not set")

        self._table_ready = False

    def get_configuration(self) -> dict:
        return {"host": self.host, "port": self.port, "db_name": self.db_name}

    def _connect(self) -> psycopg.Connection:
        """Synchronous connect - always run this through asyncio.to_thread()."""
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.db_name,
            user=self.user,
            password=self.password,
        )

    def _ensure_table_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_EMBEDDING_CACHE_TABLE)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _get_many_sync(self, content_hashes: list[str], embedding_model: str) -> dict[str, list[float]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content_hash, embedding FROM embedding_cache "
                    "WHERE embedding_model = %s AND content_hash = ANY(%s)",
                    (embedding_model, content_hashes),
                )
                return {row[0]: json.loads(row[1]) for row in cur.fetchall()}

    async def get_many(self, content_hashes: list[str], embedding_model: str) -> dict[str, list[float]]:
        """Returns {content_hash: embedding} for whichever of the given hashes are cached - missing hashes are simply absent, never raises on a miss."""
        if not content_hashes:
            return {}
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "embedding_cache.get_many", count=len(content_hashes)):
            return await asyncio.to_thread(self._get_many_sync, content_hashes, embedding_model)

    def _set_many_sync(self, entries: list[tuple[str, list[float]]], embedding_model: str) -> None:
        with self._connect() as conn:
            for content_hash, embedding in entries:
                conn.execute(
                    "INSERT INTO embedding_cache (content_hash, embedding_model, embedding) VALUES (%s, %s, %s) "
                    "ON CONFLICT (content_hash, embedding_model) DO NOTHING",
                    (content_hash, embedding_model, json.dumps(embedding)),
                )
            conn.commit()

    async def set_many(self, entries: list[tuple[str, list[float]]], embedding_model: str) -> None:
        if not entries:
            return
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "embedding_cache.set_many", count=len(entries)):
            await asyncio.to_thread(self._set_many_sync, entries, embedding_model)

    def health_check(self) -> dict:
        """Report whether this cache is usable - connects, creates the table if missing, counts rows."""
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.host:
            result["status"] = "unhealthy"
            result["message"] = "POSTGRES_DB_HOST not set"
            return result

        try:
            with self._connect() as conn:
                conn.execute(CREATE_EMBEDDING_CACHE_TABLE)
                conn.commit()
                row = conn.execute("SELECT count(*) FROM embedding_cache").fetchone()
            result["status"] = "healthy"
            result["entries_cached"] = row[0]
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
