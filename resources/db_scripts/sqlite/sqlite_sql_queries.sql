-- ============================================================================
-- SQLite SQL Queries for Document Indexing
-- ============================================================================
-- This file contains all SQL DML statements used by sqlite_db_client.py
-- Queries are identified by -- NAME: markers and loaded at runtime.
--
-- Naming Convention:
--   - INSERT_* : Insert or replace operations
--   - SELECT_* : Read operations
--   - DELETE_* : Delete operations
--   - COUNT_*  : Aggregation operations
--
-- IMPORTANT: Queries that support dynamic WHERE clauses should NOT end with
-- semicolons as the WHERE clause is appended at runtime.
-- ============================================================================


-- ============================================================================
-- DOCUMENT METADATA OPERATIONS
-- ============================================================================

-- NAME: INSERT_DOCUMENT_METADATA
INSERT OR REPLACE INTO documents_metadata (
    id,
    namespace,
    file_name,
    file_type,
    file_hash,
    file_version,
    tags,
    language,
    model_version,
    chunk_profile,
    chunk_size,
    chunk_overlap,
    model_dim,
    external_id,
    title,
    vector_store,
    created_at,
    updated_at
) VALUES (
    :id,
    :namespace,
    :file_name,
    :file_type,
    :file_hash,
    :file_version,
    :tags,
    :language,
    :model_version,
    :chunk_profile,
    :chunk_size,
    :chunk_overlap,
    :model_dim,
    :external_id,
    :title,
    :vector_store,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_DOCUMENTS_METADATA
SELECT
    id,
    namespace,
    file_name,
    file_type,
    file_hash,
    file_version,
    tags,
    language,
    model_version,
    chunk_profile,
    chunk_size,
    chunk_overlap,
    model_dim,
    external_id,
    title,
    vector_store,
    created_at,
    updated_at
FROM documents_metadata
{where}
ORDER BY created_at DESC
LIMIT ? OFFSET ?

-- NAME: COUNT_DOCUMENTS
SELECT COUNT(1) FROM documents_metadata

-- NAME: DELETE_DOCUMENT_METADATA
DELETE FROM documents_metadata
WHERE id = ? AND namespace = ?


-- ============================================================================
-- CHUNK METADATA OPERATIONS
-- ============================================================================

-- NAME: INSERT_CHUNK_METADATA_BATCH
INSERT OR REPLACE INTO chunks_metadata (
    id,
    document_id,
    parent_id,
    chunk_index,
    token_count,
    created_at,
    updated_at
) VALUES (
    :id,
    :document_id,
    :parent_id,
    :chunk_index,
    :token_count,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)

-- NAME: SELECT_CHUNKS_METADATA
SELECT
    id,
    document_id,
    parent_id,
    chunk_index,
    token_count,
    created_at,
    updated_at
FROM chunks_metadata
{where}
ORDER BY document_id, chunk_index
LIMIT ? OFFSET ?

-- NAME: SELECT_CHUNK_INDEXES_FOR_DOC
SELECT chunk_index
FROM chunks_metadata
WHERE document_id = ?
ORDER BY chunk_index

-- NAME: COUNT_CHUNKS
SELECT COUNT(1)
FROM chunks_metadata c
JOIN documents_metadata d ON c.document_id = d.id

-- NAME: COUNT_CHUNKS_BY_NAMESPACE
SELECT COUNT(1)
FROM chunks_metadata c
JOIN documents_metadata d ON c.document_id = d.id
WHERE d.namespace = ?


-- ============================================================================
-- CHUNK DELETE OPERATIONS
-- ============================================================================

-- NAME: DELETE_CHUNKS_BY_IDS
DELETE FROM chunks_metadata
WHERE id IN ({placeholders})

-- NAME: DELETE_CHUNKS_BY_DOCUMENT_ID
DELETE FROM chunks_metadata
WHERE document_id = ?

-- NAME: DELETE_CHUNKS_BY_PARENT_ID
DELETE FROM chunks_metadata
WHERE parent_id = ?

-- NAME: DELETE_CHUNKS_BY_INDEXES
DELETE FROM chunks_metadata
WHERE document_id = ? AND chunk_index IN ({placeholders})

-- NAME: SELECT_CHUNKS_BY_INDEXES
SELECT id, chunk_index
FROM chunks_metadata
WHERE document_id = ? AND chunk_index IN ({placeholders})
