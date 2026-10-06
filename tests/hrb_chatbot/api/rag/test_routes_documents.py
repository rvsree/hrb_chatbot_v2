"""Tests for POST/GET/DELETE /v1/genai-rag/ingest-document/documents (api/rag/ingest_document.py).
Phase 26: upload now indexes immediately (one endpoint, no separate
/index step) - pipeline.index_document() is faked for every test here
(see _fake_indexing below) so no test spends real embedding API cost.

Phase 45: identity travels as a JSON payload on every request, including
GET/DELETE (non-standard HTTP, deliberate - see
docs/agent-reference/endpoint-request-response-contracts.md) - not headers, not query params.

Phase 96: the three GET routes (list/get-by-id/cleanup-preview) are the one
exception - a real browser can't send a body on GET at all (Fetch spec),
so those three read identity from query params instead. POST/DELETE below
are unaffected."""

import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app
from src.hrb_chatbot.models.documents import MAX_FILE_SIZE_BYTES
from src.hrb_chatbot.services import documents_service

client = TestClient(app)

HR_SUPPORT_USER_PROFILE = {"employee_id": "EMP051", "full_name": "Hana Support", "role": "hr_support"}


@pytest.fixture(autouse=True)
def _no_op_answer_cache_invalidation(monkeypatch):
    """This file's own metadata_store/vector_store are real-but-local (test-isolated
    SQLite, local-persistent Chroma - no network call either way). Phase 78's answer
    cache is Postgres, a genuine network service - no-op it here so this file keeps
    its existing no-real-network-call property, matching every other test in this
    suite (documents_service._clear_answer_cache_best_effort already swallows a real
    failure in production; this just skips the real connection attempt in tests)."""

    async def _noop():
        return None

    monkeypatch.setattr(documents_service, "_clear_answer_cache_best_effort", _noop)


def _payload(user_profile=None, chunk_info=None, document_metadata=None) -> dict:
    """Build the `data={"payload": ...}` kwarg for a multipart upload request."""
    body = {"user_profile": HR_SUPPORT_USER_PROFILE if user_profile is None else user_profile}
    if chunk_info is not None:
        body["chunk_info"] = chunk_info
    if document_metadata is not None:
        body["document_metadata"] = document_metadata
    return {"payload": json.dumps(body)}


def _identity_body(user_profile=None) -> dict:
    """Build the JSON body for a DELETE request's identity."""
    return {"user_profile": HR_SUPPORT_USER_PROFILE if user_profile is None else user_profile}


def _get(url: str, user_profile=None):
    # Phase 96: GET identity is query params, not a body - a real browser
    # can't send a body on GET at all (Fetch spec forbids it).
    return client.get(url, params=HR_SUPPORT_USER_PROFILE if user_profile is None else user_profile)


def _delete(url: str, user_profile=None):
    return client.request("DELETE", url, json=_identity_body(user_profile))


@pytest.fixture(autouse=True)
def _fake_indexing(monkeypatch):
    # Every upload now indexes immediately (Phase 26) - fake the pipeline
    # call so these tests never spend a real embedding call.
    async def _fake_index_document(document_id, file_path, **kwargs):
        return {
            "document_id": document_id,
            "action": "insert",
            "chunks_indexed": 1,
            "chunks_removed": 0,
            "vector_db": "chromadb",
            "chunking_strategy": "recursive",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "chunk_size": 1000,
            "chunk_overlap": 150,
            "document_version": 1,
            "document_metadata": {
                "owner": None, "department": None, "doc_category": None, "purpose": None,
                "doc_description": None, "effective_date": None, "audience": None,
                "confidentiality_level": None,
            },
        }

    monkeypatch.setattr(documents_service.pipeline, "index_document", _fake_index_document)


def _pdf_file(filename: str = "policy.pdf", content: bytes | None = None):
    # A fresh random default per call, not one shared literal - tests hit the
    # real SQLite DB with no per-test reset, and content-hash dedup (see
    # test_uploading_identical_content_twice_is_a_duplicate_not_a_new_document
    # below) means two tests uploading the same literal bytes would collide
    # with each other. Tests that want to deliberately reuse the same
    # content across two uploads still pass content= explicitly.
    if content is None:
        content = f"%PDF-1.4 fake content {uuid.uuid4().hex}".encode()
    return {"files": (filename, io.BytesIO(content), "application/pdf")}


def test_single_valid_pdf_is_uploaded_and_indexed():
    response = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(), data=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["uploaded_count"] == 1
    assert body["rejected_count"] == 0

    result = body["results"][0]
    assert result["status"] == "uploaded"
    assert result["document_id"] is not None
    assert result["error"] is None
    assert result["chunk_info"]["action"] == "insert"
    assert result["chunk_info"]["chunks_indexed"] == 1
    assert result["uploaded_by"] == "EMP051"
    # Bug found 2026-09-21: is_current was reporting null on a fresh upload.
    assert result["versioning_info"]["is_current"] is True
    assert result["versioning_info"]["supersedes"] is None


def test_chunking_strategy_size_and_overlap_form_fields_reach_the_pipeline(monkeypatch):
    captured = {}

    async def _capturing_fake_index_document(document_id, file_path, **kwargs):
        captured.update(kwargs)
        return {
            "document_id": document_id,
            "action": "insert",
            "chunks_indexed": 1,
            "chunks_removed": 0,
            "vector_db": "chromadb",
            "chunking_strategy": "recursive",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "chunk_size": 500,
            "chunk_overlap": 50,
            "document_version": 1,
            "document_metadata": {
                "owner": None, "department": None, "doc_category": None, "purpose": None,
                "doc_description": None, "effective_date": None, "audience": None,
                "confidentiality_level": None,
            },
        }

    monkeypatch.setattr(documents_service.pipeline, "index_document", _capturing_fake_index_document)

    response = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(),
        data=_payload(chunk_info={"chunking_strategy": "recursive", "chunk_size": 500, "chunk_overlap": 50}),
    )

    assert response.status_code == 200
    assert captured["chunking_strategy"] == "recursive"
    assert captured["chunk_size"] == 500
    assert captured["chunk_overlap"] == 50


def test_invalid_chunking_strategy_payload_value_returns_422_not_500():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(),
        data=_payload(chunk_info={"chunking_strategy": "not-a-real-strategy"}),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_malformed_payload_json_returns_422_not_500():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(), data={"payload": "{not valid json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_missing_payload_still_requires_identity_and_is_a_401():
    # payload omitted entirely -> {} -> user_profile is None -> 401, same
    # fail-closed behavior the old header check had.
    response = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file())

    assert response.status_code == 401


def test_uploading_with_no_files_returns_422():
    response = client.post("/v1/genai-rag/ingest-document/documents", data=_payload())

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_batch_of_two_valid_pdfs_are_both_uploaded():
    files = [
        ("files", ("policy-a.pdf", io.BytesIO(f"%PDF-1.4 fake a {uuid.uuid4().hex}".encode()), "application/pdf")),
        ("files", ("policy-b.pdf", io.BytesIO(f"%PDF-1.4 fake b {uuid.uuid4().hex}".encode()), "application/pdf")),
    ]

    response = client.post("/v1/genai-rag/ingest-document/documents", files=files, data=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["uploaded_count"] == 2
    assert body["rejected_count"] == 0

    # Each upload gets its own fresh id - not the same document twice.
    document_ids = [result["document_id"] for result in body["results"]]
    assert len(set(document_ids)) == 2


def test_non_pdf_file_is_rejected_not_the_whole_batch():
    good_content = f"%PDF-1.4 fake content {uuid.uuid4().hex}".encode()
    files = [
        ("files", ("policy.pdf", io.BytesIO(good_content), "application/pdf")),
        ("files", ("notes.txt", io.BytesIO(b"just plain text"), "text/plain")),
    ]

    response = client.post("/v1/genai-rag/ingest-document/documents", files=files, data=_payload())

    # Still 200 - a bad file in a batch is reported per-file, not a failed request.
    assert response.status_code == 200
    body = response.json()
    assert body["uploaded_count"] == 1
    assert body["rejected_count"] == 1

    rejected = [r for r in body["results"] if r["status"] == "rejected"][0]
    assert rejected["filename"] == "notes.txt"
    assert "PDF" in rejected["error"]
    assert rejected["document_id"] is None
    assert rejected["error_code"] == "INVALID_FILE_TYPE"


def test_empty_file_is_rejected():
    response = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(content=b""), data=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["rejected_count"] == 1
    assert "empty" in body["results"][0]["error"].lower()
    assert body["results"][0]["error_code"] == "EMPTY_FILE"


def test_oversized_file_is_rejected():
    too_big = b"x" * (MAX_FILE_SIZE_BYTES + 1)

    response = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(content=too_big), data=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["rejected_count"] == 1
    assert "exceeds" in body["results"][0]["error"].lower()
    assert body["results"][0]["error_code"] == "FILE_TOO_LARGE"


def test_no_files_field_at_all_is_a_422():
    response = client.post("/v1/genai-rag/ingest-document/documents", files={}, data=_payload())

    assert response.status_code == 422


def test_uploaded_document_appears_in_list_and_get_by_id():
    upload_response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="findable.pdf"), data=_payload()
    )
    document_id = upload_response.json()["results"][0]["document_id"]

    list_response = _get("/v1/genai-rag/ingest-document/documents")
    assert list_response.status_code == 200
    all_ids = [doc["id"] for doc in list_response.json()["documents"]]
    assert document_id in all_ids

    get_response = _get(f"/v1/genai-rag/ingest-document/documents/{document_id}")
    assert get_response.status_code == 200
    document = get_response.json()
    assert document["filename"] == "findable.pdf"
    # Fake pipeline.index_document() returns a result dict but doesn't touch
    # the DB (the real write_chunks() does that internally) - status stays
    # "uploaded" here, same as documents_service.create_document() set it.
    assert document["status"] == "uploaded"
    assert document["uploaded_by"] == "EMP051"


def test_get_unknown_document_id_is_a_404_with_the_standard_error_shape():
    response = _get("/v1/genai-rag/ingest-document/documents/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["code"] == "DOCUMENT_NOT_FOUND"


def test_deleting_an_indexed_document_removes_it():
    upload_response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="to-delete.pdf"), data=_payload()
    )
    document_id = upload_response.json()["results"][0]["document_id"]

    delete_response = _delete(f"/v1/genai-rag/ingest-document/documents/{document_id}")

    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["document_id"] == document_id
    assert body["filename"] == "to-delete.pdf"
    assert body["deleted_by"] == "EMP051"

    # Really gone, not just reported as deleted.
    get_response = _get(f"/v1/genai-rag/ingest-document/documents/{document_id}")
    assert get_response.status_code == 404

    list_response = _get("/v1/genai-rag/ingest-document/documents")
    all_ids = [doc["id"] for doc in list_response.json()["documents"]]
    assert document_id not in all_ids


def test_deleting_an_unknown_document_id_is_a_404():
    response = _delete("/v1/genai-rag/ingest-document/documents/does-not-exist")

    assert response.status_code == 404
    assert "error" in response.json()


def test_deleting_the_same_document_twice_is_404_the_second_time():
    upload_response = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(), data=_payload())
    document_id = upload_response.json()["results"][0]["document_id"]

    first_delete = _delete(f"/v1/genai-rag/ingest-document/documents/{document_id}")
    second_delete = _delete(f"/v1/genai-rag/ingest-document/documents/{document_id}")

    assert first_delete.status_code == 200
    assert second_delete.status_code == 404


def test_uploading_identical_content_twice_is_a_duplicate_not_a_new_document():
    # uuid-salted, not a fixed literal - this hits the real, persistent
    # SQLite DB (no per-test reset), so a fixed literal would start matching
    # leftover rows from a previous test *run*, not just within this one.
    same_content = f"%PDF-1.4 identical bytes both times {uuid.uuid4().hex}".encode()

    first = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(content=same_content), data=_payload())
    second = client.post("/v1/genai-rag/ingest-document/documents", files=_pdf_file(content=same_content), data=_payload())

    assert first.json()["results"][0]["status"] == "uploaded"
    first_document_id = first.json()["results"][0]["document_id"]

    second_body = second.json()
    assert second_body["uploaded_count"] == 0
    assert second_body["duplicate_count"] == 1
    assert second_body["rejected_count"] == 0

    duplicate_result = second_body["results"][0]
    assert duplicate_result["status"] == "duplicate"
    # Points back at the FIRST upload's document - no second document was created.
    assert duplicate_result["document_id"] == first_document_id
    assert duplicate_result["message"] is not None
    assert first_document_id in duplicate_result["message"]
    # Same bug as the fresh-upload case: versioning_info must reflect the
    # EXISTING document's real row, not default to null.
    assert duplicate_result["versioning_info"]["is_current"] is True


def test_identical_content_under_a_different_filename_is_still_a_duplicate():
    same_content = f"%PDF-1.4 same bytes, different name {uuid.uuid4().hex}".encode()

    first = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="v1.pdf", content=same_content), data=_payload()
    )
    second = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(filename="renamed-copy.pdf", content=same_content),
        data=_payload(),
    )

    first_document_id = first.json()["results"][0]["document_id"]
    second_result = second.json()["results"][0]
    assert second_result["status"] == "duplicate"
    assert second_result["document_id"] == first_document_id


def test_same_filename_with_different_content_is_not_a_duplicate():
    run_id = uuid.uuid4().hex
    first = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(filename="policy.pdf", content=f"%PDF-1.4 version one {run_id}".encode()),
        data=_payload(),
    )
    second = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(filename="policy.pdf", content=f"%PDF-1.4 version two {run_id}".encode()),
        data=_payload(),
    )

    assert second.json()["results"][0]["status"] == "uploaded"
    first_id = first.json()["results"][0]["document_id"]
    second_id = second.json()["results"][0]["document_id"]
    assert first_id != second_id


def test_supersedes_document_id_on_a_batch_upload_is_rejected_as_ambiguous():
    files = [
        ("files", ("a.pdf", io.BytesIO(f"%PDF-1.4 a {uuid.uuid4().hex}".encode()), "application/pdf")),
        ("files", ("b.pdf", io.BytesIO(f"%PDF-1.4 b {uuid.uuid4().hex}".encode()), "application/pdf")),
    ]

    response = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=files,
        data=_payload(document_metadata={"supersedes_document_id": "some-id"}),
    )

    assert response.status_code == 422


def test_supersedes_document_id_pointing_at_an_unknown_document_is_rejected():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(),
        data=_payload(document_metadata={"supersedes_document_id": "does-not-exist"}),
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "rejected"
    assert "does-not-exist" in result["error"]
    assert result["error_code"] == "SUPERSEDES_TARGET_NOT_FOUND"


def test_supersedes_document_id_on_a_valid_target_is_recorded_on_the_new_document():
    target_response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="v1.pdf"), data=_payload()
    )
    target_id = target_response.json()["results"][0]["document_id"]

    response = client.post(
        "/v1/genai-rag/ingest-document/documents",
        files=_pdf_file(filename="v2.pdf"),
        data=_payload(document_metadata={"supersedes_document_id": target_id}),
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "uploaded"
    new_document_id = result["document_id"]

    new_document = _get(f"/v1/genai-rag/ingest-document/documents/{new_document_id}").json()
    assert new_document["versioning_info"]["supersedes"] == target_id


def test_ingestion_without_any_identity_is_a_401():
    response = client.get("/v1/genai-rag/ingest-document/documents")

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHENTICATED"


def test_ingestion_with_an_unknown_role_value_is_a_401():
    response = _get(
        "/v1/genai-rag/ingest-document/documents",
        {"employee_id": "EMP051", "full_name": "Hana Support", "role": "made-up-role"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHENTICATED"
    assert "made-up-role" in body["error"]


def test_ingestion_as_employee_or_manager_is_a_403_only_hr_support_may_upload():
    for role in ("employee", "manager"):
        response = client.post(
            "/v1/genai-rag/ingest-document/documents",
            files=_pdf_file(),
            data=_payload(user_profile={"employee_id": "EMP052", "full_name": "Some Employee", "role": role}),
        )

        assert response.status_code == 403, role
        body = response.json()
        assert body["code"] == "FORBIDDEN"
        assert "hr_support" in body["error"]


def test_the_separate_index_endpoint_no_longer_exists():
    # Phase 26 - upload does the whole pipeline in one call now.
    response = client.post("/v1/genai-rag/ingest-document/documents/does-not-exist/index")

    assert response.status_code == 404


def test_cleanup_preview_lists_test_noise_without_deleting_it():
    # Phase 46: _pdf_file()'s fake content ("%PDF-1.4 fake content <uuid>")
    # is well under the 1024-byte threshold - a real regression test, not
    # faked, since tests now hit an isolated DB (data/test_sqlite_db.sqlite3),
    # not the real dev one.
    upload_response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="noise.pdf"), data=_payload()
    )
    document_id = upload_response.json()["results"][0]["document_id"]

    preview_response = _get("/v1/genai-rag/ingest-document/documents/cleanup/preview")

    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["threshold_bytes"] == 1024
    matched_ids = [doc["id"] for doc in body["documents"]]
    assert document_id in matched_ids
    assert body["count"] == len(body["documents"])

    # Still there - preview must not delete anything.
    assert _get(f"/v1/genai-rag/ingest-document/documents/{document_id}").status_code == 200


def test_cleanup_delete_removes_test_noise_and_reports_deleted_by():
    upload_response = client.post(
        "/v1/genai-rag/ingest-document/documents", files=_pdf_file(filename="noise-to-delete.pdf"), data=_payload()
    )
    document_id = upload_response.json()["results"][0]["document_id"]

    delete_response = _delete("/v1/genai-rag/ingest-document/documents/cleanup")

    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["documents_deleted"] >= 1
    assert body["deleted_by"] == "EMP051"

    # Really gone.
    assert _get(f"/v1/genai-rag/ingest-document/documents/{document_id}").status_code == 404


def test_cleanup_routes_are_not_shadowed_by_the_document_id_route():
    # "cleanup" must never be read as a document_id - both new routes are
    # registered before GET/DELETE /documents/{document_id} for this reason.
    response = _get("/v1/genai-rag/ingest-document/documents/cleanup/preview")

    assert response.status_code == 200
    assert "threshold_bytes" in response.json()  # not the 404 error shape


def test_delete_all_calls_the_service_and_returns_its_result(monkeypatch):
    # Faked, not a real call - the real delete_all_documents() wipes the
    # ENTIRE dev DB, including whatever a person is testing manually via
    # Postman at the same time (confirmed live - this used to run for
    # real here and deleted a user's in-progress test document).
    async def _fake_delete_all(deleted_by=None):
        return {"documents_deleted": 3, "chunks_removed": 12, "deleted_by": deleted_by}

    monkeypatch.setattr(documents_service, "delete_all_documents", _fake_delete_all)

    response = _delete("/v1/genai-rag/ingest-document/documents")

    assert response.status_code == 200
    assert response.json() == {"documents_deleted": 3, "chunks_removed": 12, "deleted_by": "EMP051"}


@pytest.fixture(autouse=True)
def _fake_presigned_url(monkeypatch):
    # Phase 89: generate_presigned_upload_url() calls boto3 - fake it here
    # too, same no-real-AWS-call guarantee as every other test in this file.
    def _fake_generate(document_id, filename, content_type):
        return {"upload_url": f"https://hrb-chatbot-kb-uploads.s3.amazonaws.com/{document_id}/{filename}", "expires_in_seconds": 300}

    monkeypatch.setattr(documents_service, "generate_presigned_upload_url", _fake_generate)


def test_presigned_upload_returns_a_url_and_a_pending_document(monkeypatch):
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={"user_profile": HR_SUPPORT_USER_PROFILE, "filename": "401k-policy.pdf", "content_type": "application/pdf"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_upload"
    assert body["expires_in_seconds"] == 300
    assert body["document_id"] in body["upload_url"]

    document = _get(f"/v1/genai-rag/ingest-document/documents/{body['document_id']}").json()
    assert document["status"] == "pending_upload"
    assert document["filename"] == "401k-policy.pdf"


def test_presigned_upload_rejects_a_non_pdf_content_type():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={"user_profile": HR_SUPPORT_USER_PROFILE, "filename": "notes.txt", "content_type": "text/plain"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_FILE_TYPE"


def test_presigned_upload_rejects_an_unknown_supersedes_target():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={
            "user_profile": HR_SUPPORT_USER_PROFILE,
            "filename": "401k-policy.pdf",
            "content_type": "application/pdf",
            "document_metadata": {"supersedes_document_id": "does-not-exist"},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "SUPERSEDES_TARGET_NOT_FOUND"


def test_presigned_upload_as_employee_is_a_403():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={
            "user_profile": {"employee_id": "EMP052", "full_name": "Some Employee", "role": "employee"},
            "filename": "401k-policy.pdf",
            "content_type": "application/pdf",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_presigned_upload_stashes_chunk_info_and_document_metadata_overrides_for_the_lambda():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={
            "user_profile": HR_SUPPORT_USER_PROFILE,
            "filename": "401k-policy.pdf",
            "content_type": "application/pdf",
            "chunk_info": {"chunking_strategy": "recursive", "chunk_size": 800, "chunk_overlap": 100},
            "document_metadata": {"doc_category": "benefits", "department": "HR"},
        },
    )
    document_id = response.json()["document_id"]

    import asyncio

    from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway

    document = asyncio.run(get_db_gateway().metadata_store().get_document(document_id))
    overrides = json.loads(document["pending_overrides"])
    assert overrides["chunk_info"] == {"chunking_strategy": "recursive", "chunk_size": 800, "chunk_overlap": 100}
    assert overrides["document_metadata"]["doc_category"] == "benefits"


def test_presigned_upload_without_overrides_leaves_pending_overrides_null():
    response = client.post(
        "/v1/genai-rag/ingest-document/documents/presigned-upload",
        json={"user_profile": HR_SUPPORT_USER_PROFILE, "filename": "401k-policy.pdf", "content_type": "application/pdf"},
    )
    document_id = response.json()["document_id"]

    import asyncio

    from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway

    document = asyncio.run(get_db_gateway().metadata_store().get_document(document_id))
    assert document["pending_overrides"] is None
