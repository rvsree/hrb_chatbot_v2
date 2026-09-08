CREATE TABLE IF NOT EXISTS documents_metadata (
                                                  id TEXT PRIMARY KEY,
                                                  namespace TEXT,
                                                  file_name TEXT,
                                                  file_type TEXT,
                                                  file_hash TEXT,
                                                  file_version TEXT,
                                                  tags TEXT,
                                                  language TEXT,
                                                  model_version TEXT,
                                                  chunk_profile TEXT,
                                                  chunk_size INTEGER,
                                                  chunk_overlap INTEGER,
                                                  model_dim INTEGER,
                                                  external_id TEXT,
                                                  title TEXT,
                                                  vector_store TEXT,
                                                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS chunks_metadata (
                                               id TEXT PRIMARY KEY,
                                               document_id TEXT,
                                               parent_id TEXT,
                                               chunk_index INTEGER,
                                               token_count INTEGER,
                                               created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                               updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                               FOREIGN KEY(document_id) REFERENCES documents_metadata(id) ON DELETE CASCADE
);
