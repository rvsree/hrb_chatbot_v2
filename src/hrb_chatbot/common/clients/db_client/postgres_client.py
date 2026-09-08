"""Postgres client - an alternative document-metadata store to SQLite.

Same `documents` table shape as sqlite_client.py, same BaseMetadataClient
contract - the two are interchangeable behind db_gateway.py. SQLite is what
documents_service.py actually calls today; this exists, fully working and
tested on its own, so switching the active store later is a config change
plus a gateway call, not new code.

Why sync psycopg wrapped in asyncio.to_thread, not psycopg's native async API
---------------------------------------------------------------------------------
psycopg.AsyncConnection genuinely does not work on Windows under the default
asyncio event loop (ProactorEventLoop) - it raises InterfaceError on
connect(), confirmed while building this. The fix is not to change the
process-wide event loop policy (uvicorn on Windows relies on Proactor for
other things), it's to not use psycopg's async driver at all: run the
ordinary synchronous psycopg.connect() calls inside asyncio.to_thread(),
which is exactly what aiosqlite itself does internally for sqlite3 (which
has no async driver either). Same portability, same non-blocking behaviour
for the event loop, and it happens to work identically on Linux too - so
this is the more portable choice for the eventual AWS deployment, not a
Windows-only workaround.

Why a fresh connection per call, not a pool
-----------------------------------------------
psycopg-pool is in requirements.txt and would be the right choice under
real concurrent load. For this project's current scope, matching
sqlite_client.py's own "connect, do one thing, close" style keeps both
clients readable the same way - pooling is a legitimate later optimization,
not a correctness requirement yet.

Why the table is created lazily, on first real use
-------------------------------------------------------
Same reasoning as every other client here: health_check(deep=False) must
stay instant and touch nothing.
"""

import asyncio
import json

import psycopg

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("postgres_client")

CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
)
"""

# chunk_ids was added after this table already existed - CREATE TABLE IF NOT
# EXISTS is a no-op against a table that's already there. Postgres (unlike
# SQLite) supports IF NOT EXISTS on ADD COLUMN directly, so this needs no
# try/except.
ADD_CHUNK_IDS_COLUMN = "ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_ids TEXT"


class PostgresClient(BaseMetadataClient):
    """Stores document metadata in Postgres."""

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
        """Return the settings this client is using - no password in it."""
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
            conn.execute(CREATE_DOCUMENTS_TABLE)
            conn.execute(ADD_CHUNK_IDS_COLUMN)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return

        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _create_document_sync(self, document_id: str, filename: str, file_path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, filename, file_path, status, error_message, "
                "created_at, updated_at) VALUES (%s, %s, %s, 'uploaded', NULL, now(), now())",
                (document_id, filename, file_path),
            )
            conn.commit()

    async def create_document(self, document_id: str, filename: str, file_path: str) -> None:
        await self._ensure_table()
        await asyncio.to_thread(self._create_document_sync, document_id, filename, file_path)

    def _update_status_sync(self, document_id: str, status: str, error_message: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE documents SET status = %s, error_message = %s, updated_at = now() "
                "WHERE id = %s",
                (status, error_message, document_id),
            )
            conn.commit()

    async def update_status(
        self, document_id: str, status: str, error_message: str | None = None
    ) -> None:
        await self._ensure_table()
        await asyncio.to_thread(self._update_status_sync, document_id, status, error_message)

    def _set_chunk_ids_sync(self, document_id: str, chunk_ids: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE documents SET chunk_ids = %s, updated_at = now() WHERE id = %s",
                (json.dumps(chunk_ids), document_id),
            )
            conn.commit()

    async def set_chunk_ids(self, document_id: str, chunk_ids: list[str]) -> None:
        await self._ensure_table()
        await asyncio.to_thread(self._set_chunk_ids_sync, document_id, chunk_ids)

    def _get_document_sync(self, document_id: str) -> dict | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=self._dict_row_factory) as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
                return cur.fetchone()

    async def get_document(self, document_id: str) -> dict | None:
        await self._ensure_table()
        return await asyncio.to_thread(self._get_document_sync, document_id)

    def _list_documents_sync(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor(row_factory=self._dict_row_factory) as cur:
                cur.execute("SELECT * FROM documents ORDER BY created_at DESC")
                return cur.fetchall()

    async def list_documents(self) -> list[dict]:
        await self._ensure_table()
        return await asyncio.to_thread(self._list_documents_sync)

    @staticmethod
    def _dict_row_factory(cursor):
        """Turn each result row into a dict keyed by column name.

        psycopg's built-in dict_row does the same thing - this is written
        out rather than imported so the shape returned matches
        sqlite_client.py's aiosqlite.Row-to-dict conversion exactly, with no
        surprises about a datetime object where SQLite would give a string.
        """
        columns = [desc.name for desc in cursor.description]

        def make_row(values):
            row = dict(zip(columns, values, strict=True))
            for key in ("created_at", "updated_at"):
                if row.get(key) is not None:
                    row[key] = row[key].isoformat()
            return row

        return make_row

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only reports the configured connection settings - no
        socket is opened.
        deep=True: connects for real, creates the table if missing (same as
        Postgres always does for a fresh database), and counts rows. This
        runs synchronously - health_check is not async on any client in this
        project, and it runs once per health check, not per request.
        """
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.host:
            result["status"] = "unhealthy"
            result["message"] = "POSTGRES_DB_HOST not configured"
            return result

        if not deep:
            result["status"] = "configured"
            return result

        try:
            connection = psycopg.connect(
                host=self.host,
                port=self.port,
                dbname=self.db_name,
                user=self.user,
                password=self.password,
                connect_timeout=5,
            )
            try:
                connection.execute(CREATE_DOCUMENTS_TABLE)
                connection.execute(ADD_CHUNK_IDS_COLUMN)
                connection.commit()
                document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            finally:
                connection.close()

            result["status"] = "healthy"
            result["documents_stored"] = document_count
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
