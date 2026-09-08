"""Tests for IdempotencyStore - common/idempotency/idempotency_store.py."""

import time

from src.hrb_chatbot.common.idempotency.idempotency_store import IdempotencyStore


def test_unseen_key_returns_none():
    store = IdempotencyStore()
    assert store.get("never-seen-key") is None


def test_a_stored_response_is_returned_for_the_same_key():
    store = IdempotencyStore()
    store.set("key-1", 200, {"document_id": "abc"})

    cached = store.get("key-1")

    assert cached == (200, {"document_id": "abc"})


def test_an_expired_entry_is_treated_as_unseen():
    # A 0-second TTL means the entry is stale the instant it's checked.
    store = IdempotencyStore(ttl_seconds=0)
    store.set("key-1", 200, {"document_id": "abc"})

    time.sleep(0.01)

    assert store.get("key-1") is None


def test_different_keys_are_independent():
    store = IdempotencyStore()
    store.set("key-1", 200, {"result": "first"})
    store.set("key-2", 200, {"result": "second"})

    assert store.get("key-1") == (200, {"result": "first"})
    assert store.get("key-2") == (200, {"result": "second"})
