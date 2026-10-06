"""Shared content-hash helper - was written out independently in
documents_service.py (Phase 16) and index_document_handler.py (Phase 88)
for the same purpose, extracted here during Phase 93's cleanup pass."""

import hashlib


def compute_content_hash(content: bytes) -> str:
    """SHA-256 of raw file bytes - the dedup key passed to find_by_content_hash()/create_document()."""
    return hashlib.sha256(content).hexdigest()
