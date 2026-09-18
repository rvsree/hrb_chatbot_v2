"""Phase 28 regression: a document's first successful index must report
document_version 1, not 2. Direct against SQLiteClient - no HTTP, no
embedding cost, real SQLite (a fresh temp file per test)."""

import tempfile
import uuid
from pathlib import Path

from src.hrb_chatbot.common.clients.db_client.sqlite_client import SQLiteClient


async def test_first_successful_index_reports_version_1_not_2():
    db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
    client = SQLiteClient(db_path=str(db_path))
    document_id = uuid.uuid4().hex

    await client.create_document(document_id, "policy.pdf", "data/uploads/x/policy.pdf", 100, "hash1")
    created = await client.get_document(document_id)
    assert created["document_version"] == 0  # nothing indexed yet

    first_version = await client.record_successful_index(
        document_id, ["chunk1"], embedding_model="text-embedding-3-small",
        embedding_dimension=1536, vector_db="chromadb", chunk_size=1000, chunk_overlap=150,
    )
    assert first_version == 1  # first real index - not 2

    second_version = await client.record_successful_index(
        document_id, ["chunk1", "chunk2"], embedding_model="text-embedding-3-small",
        embedding_dimension=1536, vector_db="chromadb", chunk_size=1000, chunk_overlap=150,
    )
    assert second_version == 2  # a real re-index still increments normally

    db_path.unlink(missing_ok=True)
