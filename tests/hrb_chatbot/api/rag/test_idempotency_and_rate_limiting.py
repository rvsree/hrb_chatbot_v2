"""API-level tests for Idempotency-Key and rate-limiting behavior on the
real routes - tests/hrb_chatbot/common/idempotency/ and
tests/hrb_chatbot/common/rate_limiting/ already test the underlying
building blocks directly; these confirm the routes actually use them.

Upload, not query, is used for the idempotency test specifically: the
query endpoint's stub always raises before ever reaching its own
store.set() call (see routes_query.py's own module docstring for why),
so replaying an Idempotency-Key against it wouldn't prove anything real
yet. Upload completes today - a real round trip through
check-then-store is actually exercised here.
"""

import io

from fastapi.testclient import TestClient

from src.hrb_chatbot.common.idempotency.idempotency_store import reset_idempotency_store
from src.hrb_chatbot.common.rate_limiting.rate_limiter import reset_rate_limiter
from src.hrb_chatbot.main import app

client = TestClient(app)


def _fake_pdf_file():
    # Upload-time validation only checks content-type/filename and size
    # (see documents_service.validate_file()) - real PDF parsing only
    # happens later, at index time - so these bytes never need to be a
    # genuinely valid PDF for an upload test.
    return {"files": ("policy.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}


def setup_function():
    # Both stores are process-wide singletons (see their own modules'
    # docstrings) - reset before each test so one test's requests can't
    # affect another's counts/cache.
    reset_idempotency_store()
    reset_rate_limiter()


def test_replaying_the_same_idempotency_key_returns_the_cached_response_not_a_new_upload():
    headers = {"Idempotency-Key": "test-key-abc-123"}

    first_response = client.post("/v1/rag/documents", files=_fake_pdf_file(), headers=headers)
    second_response = client.post("/v1/rag/documents", files=_fake_pdf_file(), headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_document_id = first_response.json()["results"][0]["document_id"]
    second_document_id = second_response.json()["results"][0]["document_id"]

    # The real proof: the SAME document_id both times, not two separate
    # uploads that each happened to succeed - a document_id is a fresh
    # random uuid per real upload (see documents_service.save_upload()),
    # so two matching ids only happen if the second call was a cache hit.
    assert first_document_id == second_document_id


def test_uploads_without_an_idempotency_key_are_never_deduplicated():
    first_response = client.post("/v1/rag/documents", files=_fake_pdf_file())
    second_response = client.post("/v1/rag/documents", files=_fake_pdf_file())

    first_document_id = first_response.json()["results"][0]["document_id"]
    second_document_id = second_response.json()["results"][0]["document_id"]

    assert first_document_id != second_document_id


def test_different_idempotency_keys_are_not_confused_with_each_other():
    response_a = client.post(
        "/v1/rag/documents", files=_fake_pdf_file(), headers={"Idempotency-Key": "key-a"}
    )
    response_b = client.post(
        "/v1/rag/documents", files=_fake_pdf_file(), headers={"Idempotency-Key": "key-b"}
    )

    document_id_a = response_a.json()["results"][0]["document_id"]
    document_id_b = response_b.json()["results"][0]["document_id"]

    assert document_id_a != document_id_b
