"""Tests for the shared content-hash helper (Phase 93 - extracted from a
real duplicate between documents_service.py and index_document_handler.py)."""

import hashlib

from src.hrb_chatbot.common.utils.content_hash import compute_content_hash


def test_same_bytes_produce_the_same_hash():
    content = b"%PDF-1.4 identical content"
    assert compute_content_hash(content) == compute_content_hash(content)


def test_different_bytes_produce_different_hashes():
    assert compute_content_hash(b"content a") != compute_content_hash(b"content b")


def test_matches_plain_sha256_hexdigest():
    content = b"some file bytes"
    assert compute_content_hash(content) == hashlib.sha256(content).hexdigest()
