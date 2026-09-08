"""SQLite client - stores one row per uploaded document.

Why aiosqlite, not the stdlib sqlite3 module directly
--------------------------------------------------------
FastAPI route handlers here are async (UploadFile reads are async), and a
synchronous sqlite3 call blocks the whole event loop while it runs - fine for
one request in a demo, wrong to build as the default habit. aiosqlite is
already in requirements.txt for exactly this reason.

Why the table is created lazily, on first real use
-----------------------------------------------------
Same reasoning as ChromaDBClient: health_check(deep=False) must stay
instant and touch nothing. Creating the table is deferred to the first
method that actually needs it, not done in __init__.
"""

import json
import sqlite3
from datetime import UTC, datetime

import aiosqlite

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("sqlite_client")

CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

# chunk_ids was added after this table already existed in real databases (this
# project's own included), so it can't just be part of CREATE_DOCUMENTS_TABLE -
# CREATE TABLE IF NOT EXISTS is a no-op against a table that's already there.
# Older SQLite has no "ADD COLUMN IF NOT EXISTS", so the duplicate-column error
# from running this twice is caught and ignored instead.
ADD_CHUNK_IDS_COLUMN = "ALTER TABLE documents ADD COLUMN chunk_ids TEXT"


class SQLiteClient(BaseMetadataClient):
    """Stores document metadata in a local SQLite file."""

    PROVIDER_NAME = "sqlite"
    ENV_KEY = "SQLITE_DB_PATH"

    DEFAULT_DB_PATH = "data/hrb_chatbot.sqlite3"

    def __init__(self, db_path: str | None = None):
        self.db_path = read_setting(db_path, "SQLITE_DB_PATH", self.DEFAULT_DB_PATH)
        self._table_ready = False

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_DOCUMENTS_TABLE)
            try:
                await db.execute(ADD_CHUNK_IDS_COLUMN)
            except aiosqlite.OperationalError as error:
                if "duplicate column" not in str(error).lower():
                    raise
            await db.commit()

        self._table_ready = True

    async def create_document(self, document_id: str, filename: str, file_path: str) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO documents (id, filename, file_path, status, error_message, "
                "created_at, updated_at) VALUES (?, ?, ?, 'uploaded', NULL, ?, ?)",
                (document_id, filename, file_path, now, now),
            )
            await db.commit()

    async def update_status(
        self, document_id: str, status: str, error_message: str | None = None
    ) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE documents SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
                (status, error_message, now, document_id),
            )
            await db.commit()

    async def set_chunk_ids(self, document_id: str, chunk_ids: list[str]) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE documents SET chunk_ids = ?, updated_at = ? WHERE id = ?",
                (json.dumps(chunk_ids), now, document_id),
            )
            await db.commit()

    async def get_document(self, document_id: str) -> dict | None:
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            row = await cursor.fetchone()

        return dict(row) if row else None

    async def list_documents(self) -> list[dict]:
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM documents ORDER BY created_at DESC")
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this store is usable.

        deep=False: only reports the configured path - no file is touched.
        deep=True: opens the file (creating it if missing, same as SQLite
        always does) and confirms the documents table can be queried. Uses
        the synchronous sqlite3 module here on purpose - health_check is not
        async (matching every other client's health_check signature in this
        project), and this runs once per health check, not per request.
        """
        result = {"provider": self.PROVIDER_NAME, "db_path": self.db_path}

        if not deep:
            result["status"] = "configured"
            return result

        try:
            connection = sqlite3.connect(self.db_path)
            try:
                connection.execute(CREATE_DOCUMENTS_TABLE)
                try:
                    connection.execute(ADD_CHUNK_IDS_COLUMN)
                except sqlite3.OperationalError as error:
                    if "duplicate column" not in str(error).lower():
                        raise
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
