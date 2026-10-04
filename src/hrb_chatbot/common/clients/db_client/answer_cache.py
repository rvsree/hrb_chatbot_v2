"""Postgres-backed answer cache (Phase 78) - exact-match only, keyed by a
hash of the query plus every retrieval/generation parameter that could
change the answer. Never used for a conversation-memory-enabled request -
that answer depends on prior turns, not just the query alone (see
pipeline.py's own wiring). Cleared entirely on any document change
(documents_service.py's own invalidation hook) - blunt but safe, no
per-document dependency tracking. Same psycopg-via-asyncio.to_thread()
pattern as postgres_client.py/conversation_store.py/embedding_cache.py."""

import asyncio
import hashlib
import json

import psycopg

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("answer_cache")

CREATE_ANSWER_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS answer_cache (
    cache_key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    answer_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def build_cache_key(query: str, **params) -> str:
    """Hashes the query plus every parameter that could change the answer -
    employee_id is never included, since a policy answer shouldn't vary by
    who asks. Same hashlib.sha256(...).hexdigest() convention this project
    already uses for content_hash/Phase 77's hash_text()."""
    canonical = json.dumps({"query": query, **params}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AnswerCache:
    """Caches a full answer_query() result dict by its cache key."""

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
            conn.execute(CREATE_ANSWER_CACHE_TABLE)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _get_sync(self, cache_key: str) -> dict | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT answer_json FROM answer_cache WHERE cache_key = %s", (cache_key,))
                row = cur.fetchone()
                return json.loads(row[0]) if row else None

    async def get(self, cache_key: str) -> dict | None:
        """Returns None on a miss - never raises for an unknown key."""
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "answer_cache.get", cache_key=cache_key):
            return await asyncio.to_thread(self._get_sync, cache_key)

    def _set_sync(self, cache_key: str, query: str, answer: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO answer_cache (cache_key, query, answer_json) VALUES (%s, %s, %s) "
                "ON CONFLICT (cache_key) DO UPDATE SET answer_json = EXCLUDED.answer_json, created_at = now()",
                (cache_key, query, json.dumps(answer)),
            )
            conn.commit()

    async def set(self, cache_key: str, query: str, answer: dict) -> None:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "answer_cache.set", cache_key=cache_key):
            await asyncio.to_thread(self._set_sync, cache_key, query, answer)

    def _clear_all_sync(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM answer_cache")
            conn.commit()
            return cur.rowcount

    async def clear_all(self) -> int:
        """Invalidation - clears every cached answer. Called whenever a document changes."""
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "answer_cache.clear_all"):
            return await asyncio.to_thread(self._clear_all_sync)

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
                conn.execute(CREATE_ANSWER_CACHE_TABLE)
                conn.commit()
                row = conn.execute("SELECT count(*) FROM answer_cache").fetchone()
            result["status"] = "healthy"
            result["answers_cached"] = row[0]
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
