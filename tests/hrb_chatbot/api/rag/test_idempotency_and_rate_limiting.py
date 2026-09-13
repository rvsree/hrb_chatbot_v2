"""API-level tests confirming the real routes actually use the
Idempotency-Key and rate-limiting building blocks (already unit-tested
elsewhere). Upload, not query, is used for idempotency since the query
stub always raises before reaching its own store.set() call."""

import io
import uuid

from fastapi.testclient import TestClient

from src.hrb_chatbot.common.idempotency.idempotency_store import reset_idempotency_store
from src.hrb_chatbot.common.rate_limiting.rate_limiter import reset_rate_limiter
from src.hrb_chatbot.main import app

client = TestClient(app)


def _fake_pdf_file(content: bytes | None = None):
    # Upload-time validation only checks content-type/filename/size; real
    # PDF parsing happens later at index time, so these bytes need not be valid.
    # A fresh random default per call, not one shared literal - content-hash
    # dedup (documents_service.py) means two calls with identical bytes now
    # legitimately return the SAME document_id, which would corrupt any test
    # here that isn't deliberately testing that. Pass content= explicitly
    # when a test wants the same bytes on purpose (e.g. the idempotency-key
    # replay test below, which must never reach that dedup check at all).
    if content is None:
        content = f"%PDF-1.4 fake content {uuid.uuid4().hex}".encode()
    return {"files": ("policy.pdf", io.BytesIO(content), "application/pdf")}


def setup_function():
    # Both stores are process-wide singletons - reset before each test so
    # one test's requests can't affect another's counts/cache.
    reset_idempotency_store()
    reset_rate_limiter()


def test_replaying_the_same_idempotency_key_returns_the_cached_response_not_a_new_upload():
    headers = {"Idempotency-Key": "test-key-abc-123"}
    # Same content on purpose: the Idempotency-Key check happens before
    # save_uploads() is ever called a second time, so this never reaches
    # (and isn't testing) the separate content-hash dedup check.
    content = f"%PDF-1.4 replay test {uuid.uuid4().hex}".encode()

    first_response = client.post(
        "/v1/rag-ingestion/documents", files=_fake_pdf_file(content), headers=headers
    )
    second_response = client.post(
        "/v1/rag-ingestion/documents", files=_fake_pdf_file(content), headers=headers
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_document_id = first_response.json()["results"][0]["document_id"]
    second_document_id = second_response.json()["results"][0]["document_id"]

    # Proof: the SAME document_id both times - a fresh uuid is generated
    # per real upload, so matching ids only happen on a cache hit.
    assert first_document_id == second_document_id


def test_uploads_without_an_idempotency_key_of_different_content_are_never_confused():
    # Different content, no Idempotency-Key - two genuinely separate uploads,
    # so two different document_ids is still correct. (Identical content
    # WITHOUT an Idempotency-Key is a different case - content-hash dedup
    # catches that regardless of the header; see
    # test_routes_documents.py::test_uploading_identical_content_twice_is_a_duplicate_not_a_new_document.)
    first_response = client.post("/v1/rag-ingestion/documents", files=_fake_pdf_file())
    second_response = client.post("/v1/rag-ingestion/documents", files=_fake_pdf_file())

    first_document_id = first_response.json()["results"][0]["document_id"]
    second_document_id = second_response.json()["results"][0]["document_id"]

    assert first_document_id != second_document_id


def test_different_idempotency_keys_are_not_confused_with_each_other():
    response_a = client.post(
        "/v1/rag-ingestion/documents", files=_fake_pdf_file(), headers={"Idempotency-Key": "key-a"}
    )
    response_b = client.post(
        "/v1/rag-ingestion/documents", files=_fake_pdf_file(), headers={"Idempotency-Key": "key-b"}
    )

    document_id_a = response_a.json()["results"][0]["document_id"]
    document_id_b = response_b.json()["results"][0]["document_id"]

    assert document_id_a != document_id_b
