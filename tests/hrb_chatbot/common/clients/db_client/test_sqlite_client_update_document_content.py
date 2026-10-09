"""Phase 125 - update_document_content() records a new filename/file_path/
size/hash after an in-place reindex. Direct against SQLiteClient - no HTTP,
real SQLite (a fresh temp file per test)."""

import tempfile
import uuid
from pathlib import Path

from src.hrb_chatbot.common.clients.db_client.sqlite_client import SQLiteClient


async def test_update_document_content_overwrites_filename_path_size_and_hash():
    db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
    client = SQLiteClient(db_path=str(db_path))
    document_id = uuid.uuid4().hex

    await client.create_document(document_id, "original.pdf", "data/uploads/x/original.pdf", 100, "hash-v1")

    await client.update_document_content(document_id, "updated.pdf", "data/uploads/x/updated.pdf", 200, "hash-v2")

    document = await client.get_document(document_id)
    assert document["filename"] == "updated.pdf"
    assert document["file_path"] == "data/uploads/x/updated.pdf"
    assert document["file_size_bytes"] == 200
    assert document["content_hash"] == "hash-v2"
