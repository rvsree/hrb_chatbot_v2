"""SQLite client - stores one row per uploaded document.

Uses aiosqlite, not stdlib sqlite3, because FastAPI's route handlers here are
async and a synchronous sqlite3 call would block the whole event loop. The
documents table is created lazily on first real use, not in __init__, so
health_check(deep=False) stays instant and touches nothing.
"""

import json
import sqlite3
from datetime import UTC, datetime

import aiosqlite

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
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

# Each column below was added after the table already existed. SQLite has no
# ADD COLUMN IF NOT EXISTS, so the duplicate-column error from re-running any
# of these against a database that already has them is caught and ignored -
# see _ensure_table() below.
ADD_COLUMNS = [
    "ALTER TABLE documents ADD COLUMN chunk_ids TEXT",
    "ALTER TABLE documents ADD COLUMN document_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE documents ADD COLUMN chunk_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN embedding_model TEXT",
    "ALTER TABLE documents ADD COLUMN embedding_dimension INTEGER",
    "ALTER TABLE documents ADD COLUMN vector_db TEXT",
    "ALTER TABLE documents ADD COLUMN chunk_size INTEGER",
    "ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER",
    "ALTER TABLE documents ADD COLUMN last_indexed_at TEXT",
    "ALTER TABLE documents ADD COLUMN file_size_bytes INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN content_hash TEXT",
    "ALTER TABLE documents ADD COLUMN is_current INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE documents ADD COLUMN supersedes TEXT",
    "ALTER TABLE documents ADD COLUMN superseded_by TEXT",
    "ALTER TABLE documents ADD COLUMN owner TEXT",
    "ALTER TABLE documents ADD COLUMN department TEXT",
    "ALTER TABLE documents ADD COLUMN doc_type TEXT",
    "ALTER TABLE documents ADD COLUMN purpose TEXT",
]

# Speeds up find_by_content_hash() - one lookup per upload, worth an index.
CREATE_CONTENT_HASH_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash)"
)

# Normalized chunk tracking - one row per chunk, not a JSON blob on
# documents.chunk_ids - so "which chunks were created when" and "which
# chunks are still current" are real, indexable SQL queries, not
# application-code JSON parsing. See base_metadata_client.py's module docstring.
CREATE_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1
)
"""
CREATE_CHUNKS_DOCUMENT_ID_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)"
)


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
            for add_column in ADD_COLUMNS:
                try:
                    await db.execute(add_column)
                except aiosqlite.OperationalError as error:
                    if "duplicate column" not in str(error).lower():
                        raise
            await db.execute(CREATE_CONTENT_HASH_INDEX)
            await db.execute(CREATE_CHUNKS_TABLE)
            await db.execute(CREATE_CHUNKS_DOCUMENT_ID_INDEX)
            await db.commit()

        self._table_ready = True

    async def create_document(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        file_size_bytes: int,
        content_hash: str,
        supersedes: str | None = None,
    ) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(logger, "sqlite", "metadata.create_document", document_id=document_id):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO documents (id, filename, file_path, status, error_message, "
                    "created_at, updated_at, document_version, file_size_bytes, content_hash, "
                    "is_current, supersedes) VALUES (?, ?, ?, 'uploaded', NULL, ?, ?, 1, ?, ?, 1, ?)",
                    (document_id, filename, file_path, now, now, file_size_bytes, content_hash, supersedes),
                )
                await db.commit()

    async def find_by_content_hash(self, content_hash: str) -> dict | None:
        await self._ensure_table()

        with log_backend_call(logger, "sqlite", "metadata.find_by_content_hash"):
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM documents WHERE content_hash = ? ORDER BY created_at DESC LIMIT 1",
                    (content_hash,),
                )
                row = await cursor.fetchone()

        if row is None:
            return None
        return dict(row)

    async def update_status(
        self, document_id: str, status: str, error_message: str | None = None
    ) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(
            logger, "sqlite", "metadata.update_status", document_id=document_id, status=status
        ):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE documents SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
                    (status, error_message, now, document_id),
                )
                await db.commit()

    async def set_chunk_ids(self, document_id: str, chunk_ids: list[str]) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(
            logger, "sqlite", "metadata.set_chunk_ids", document_id=document_id, chunk_count=len(chunk_ids)
        ):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE documents SET chunk_ids = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(chunk_ids), now, document_id),
                )
                await db.commit()

    async def record_successful_index(
        self,
        document_id: str,
        chunk_ids: list[str],
        embedding_model: str,
        embedding_dimension: int,
        vector_db: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> int:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(
            logger, "sqlite", "metadata.record_successful_index", document_id=document_id
        ):
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "UPDATE documents SET chunk_ids = ?, chunk_count = ?, embedding_model = ?, "
                    "embedding_dimension = ?, vector_db = ?, chunk_size = ?, chunk_overlap = ?, "
                    "status = 'indexed', error_message = NULL, last_indexed_at = ?, updated_at = ?, "
                    "document_version = document_version + 1 WHERE id = ? RETURNING document_version",
                    (
                        json.dumps(chunk_ids),
                        len(chunk_ids),
                        embedding_model,
                        embedding_dimension,
                        vector_db,
                        chunk_size,
                        chunk_overlap,
                        now,
                        now,
                        document_id,
                    ),
                )
                row = await cursor.fetchone()

                # Replace this document's rows in `chunks` - delete-then-insert,
                # same diff-and-replace shape as the vector store's own stale-chunk cleanup.
                await db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
                await db.executemany(
                    "INSERT INTO chunks (chunk_id, document_id, chunk_index, created_at, is_current) "
                    "VALUES (?, ?, ?, ?, 1)",
                    [(chunk_id, document_id, index, now) for index, chunk_id in enumerate(chunk_ids)],
                )
                await db.commit()

        return row[0]

    async def mark_superseded(self, document_id: str, superseded_by: str) -> list[str]:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(
            logger, "sqlite", "metadata.mark_superseded", document_id=document_id, superseded_by=superseded_by
        ):
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT chunk_ids FROM documents WHERE id = ?", (document_id,))
                row = await cursor.fetchone()

                await db.execute(
                    "UPDATE documents SET is_current = 0, superseded_by = ?, updated_at = ? WHERE id = ?",
                    (superseded_by, now, document_id),
                )
                await db.execute(
                    "UPDATE chunks SET is_current = 0 WHERE document_id = ?", (document_id,)
                )
                await db.commit()

        if row is None or row[0] is None:
            return []
        return json.loads(row[0])

    async def record_document_metadata(
        self,
        document_id: str,
        owner: str | None,
        department: str | None,
        doc_type: str | None,
        purpose: str | None,
    ) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()

        with log_backend_call(logger, "sqlite", "metadata.record_document_metadata", document_id=document_id):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE documents SET owner = ?, department = ?, doc_type = ?, purpose = ?, "
                    "updated_at = ? WHERE id = ?",
                    (owner, department, doc_type, purpose, now, document_id),
                )
                await db.commit()

    async def get_document(self, document_id: str) -> dict | None:
        await self._ensure_table()

        with log_backend_call(logger, "sqlite", "metadata.get_document", document_id=document_id):
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
                row = await cursor.fetchone()

        if row is None:
            return None
        return dict(row)

    async def list_documents(self) -> list[dict]:
        await self._ensure_table()

        with log_backend_call(logger, "sqlite", "metadata.list_documents"):
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM documents ORDER BY created_at DESC")
                rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def delete_document(self, document_id: str) -> None:
        await self._ensure_table()

        with log_backend_call(logger, "sqlite", "metadata.delete_document", document_id=document_id):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                await db.commit()

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this store is usable. deep=False only reports the
        configured path; deep=True opens the file, creates the table if missing, and queries it."""
        result = {"provider": self.PROVIDER_NAME, "db_path": self.db_path}

        if not deep:
            result["status"] = "configured"
            return result

        try:
            connection = sqlite3.connect(self.db_path)
            try:
                connection.execute(CREATE_DOCUMENTS_TABLE)
                for add_column in ADD_COLUMNS:
                    try:
                        connection.execute(add_column)
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
