"""Tests for POST/GET /v1/rag-ingestion/documents (api/rag/routes_documents.py).
Covers the upload validation rules (services/documents_service.py's
validate_file()) and the list/get-by-id read path, end to end through
FastAPI's TestClient - the same real SQLite metadata store the app itself
uses (documents_service.py calls get_db_gateway() directly, not through an
injectable dependency, so there's no fake-store seam to patch here yet)."""

import io
import uuid

from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app
from src.hrb_chatbot.models.documents import MAX_FILE_SIZE_BYTES

client = TestClient(app)


def _pdf_file(filename: str = "policy.pdf", content: bytes | None = None):
    # A fresh random default per call, not one shared literal - tests hit the
    # real SQLite DB with no per-test reset, and content-hash dedup (see
    # test_uploading_identical_content_twice_is_a_duplicate_not_a_new_document
    # below) means two tests uploading the same literal bytes would now
    # collide with each other. Tests that want to deliberately reuse the same
    # content across two uploads still pass content= explicitly.
    if content is None:
        content = f"%PDF-1.4 fake content {uuid.uuid4().hex}".encode()
    return {"files": (filename, io.BytesIO(content), "application/pdf")}


def test_single_valid_pdf_is_uploaded():
    response = client.post("/v1/rag-ingestion/documents", files=_pdf_file())

    assert response.status_code == 200
    body = response.json()
    assert body["uploaded_count"] == 1
    assert body["rejected_count"] == 0

    result = body["results"][0]
    assert result["status"] == "uploaded"
    assert result["document_id"] is not None
    assert result["error"] is None


def test_batch_of_two_valid_pdfs_are_both_uploaded():
    files = [
        ("files", ("policy-a.pdf", io.BytesIO(f"%PDF-1.4 fake a {uuid.uuid4().hex}".encode()), "application/pdf")),
        ("files", ("policy-b.pdf", io.BytesIO(f"%PDF-1.4 fake b {uuid.uuid4().hex}".encode()), "application/pdf")),
    ]

    response = client.post("/v1/rag-ingestion/documents", files=files)

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

    response = client.post("/v1/rag-ingestion/documents", files=files)

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
    response = client.post("/v1/rag-ingestion/documents", files=_pdf_file(content=b""))

    assert response.status_code == 200
    body = response.json()
    assert body["rejected_count"] == 1
    assert "empty" in body["results"][0]["error"].lower()
    assert body["results"][0]["error_code"] == "EMPTY_FILE"


def test_oversized_file_is_rejected():
    too_big = b"x" * (MAX_FILE_SIZE_BYTES + 1)

    response = client.post("/v1/rag-ingestion/documents", files=_pdf_file(content=too_big))

    assert response.status_code == 200
    body = response.json()
    assert body["rejected_count"] == 1
    assert "exceeds" in body["results"][0]["error"].lower()
    assert body["results"][0]["error_code"] == "FILE_TOO_LARGE"


def test_no_files_field_at_all_is_a_422():
    response = client.post("/v1/rag-ingestion/documents", files={})

    assert response.status_code == 422


def test_uploaded_document_appears_in_list_and_get_by_id():
    upload_response = client.post("/v1/rag-ingestion/documents", files=_pdf_file(filename="findable.pdf"))
    document_id = upload_response.json()["results"][0]["document_id"]

    list_response = client.get("/v1/rag-ingestion/documents")
    assert list_response.status_code == 200
    all_ids = [doc["id"] for doc in list_response.json()["documents"]]
    assert document_id in all_ids

    get_response = client.get(f"/v1/rag-ingestion/documents/{document_id}")
    assert get_response.status_code == 200
    document = get_response.json()
    assert document["filename"] == "findable.pdf"
    assert document["status"] == "uploaded"


def test_get_unknown_document_id_is_a_404_with_the_standard_error_shape():
    response = client.get("/v1/rag-ingestion/documents/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["code"] == "DOCUMENT_NOT_FOUND"


def test_deleting_an_unindexed_document_removes_it_and_reports_zero_chunks():
    upload_response = client.post(
        "/v1/rag-ingestion/documents", files=_pdf_file(filename="to-delete.pdf")
    )
    document_id = upload_response.json()["results"][0]["document_id"]

    delete_response = client.delete(f"/v1/rag-ingestion/documents/{document_id}")

    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["document_id"] == document_id
    assert body["filename"] == "to-delete.pdf"
    assert body["chunks_removed"] == 0  # never indexed - nothing in the vector store to remove

    # Really gone, not just reported as deleted.
    get_response = client.get(f"/v1/rag-ingestion/documents/{document_id}")
    assert get_response.status_code == 404

    list_response = client.get("/v1/rag-ingestion/documents")
    all_ids = [doc["id"] for doc in list_response.json()["documents"]]
    assert document_id not in all_ids


def test_deleting_an_unknown_document_id_is_a_404():
    response = client.delete("/v1/rag-ingestion/documents/does-not-exist")

    assert response.status_code == 404
    assert "error" in response.json()


def test_deleting_the_same_document_twice_is_404_the_second_time():
    upload_response = client.post("/v1/rag-ingestion/documents", files=_pdf_file())
    document_id = upload_response.json()["results"][0]["document_id"]

    first_delete = client.delete(f"/v1/rag-ingestion/documents/{document_id}")
    second_delete = client.delete(f"/v1/rag-ingestion/documents/{document_id}")

    assert first_delete.status_code == 200
    assert second_delete.status_code == 404


def test_uploading_identical_content_twice_is_a_duplicate_not_a_new_document():
    # uuid-salted, not a fixed literal - this hits the real, persistent
    # SQLite DB (no per-test reset), so a fixed literal would start
    # matching leftover rows from a previous test *run*, not just within
    # this one, and break the "first upload is fresh" assumption below.
    same_content = f"%PDF-1.4 identical bytes both times {uuid.uuid4().hex}".encode()

    first = client.post("/v1/rag-ingestion/documents", files=_pdf_file(content=same_content))
    second = client.post("/v1/rag-ingestion/documents", files=_pdf_file(content=same_content))

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


def test_identical_content_under_a_different_filename_is_still_a_duplicate():
    same_content = f"%PDF-1.4 same bytes, different name {uuid.uuid4().hex}".encode()

    first = client.post("/v1/rag-ingestion/documents", files=_pdf_file(filename="v1.pdf", content=same_content))
    second = client.post(
        "/v1/rag-ingestion/documents", files=_pdf_file(filename="renamed-copy.pdf", content=same_content)
    )

    first_document_id = first.json()["results"][0]["document_id"]
    second_result = second.json()["results"][0]
    assert second_result["status"] == "duplicate"
    assert second_result["document_id"] == first_document_id


def test_same_filename_with_different_content_is_not_a_duplicate():
    run_id = uuid.uuid4().hex
    first = client.post(
        "/v1/rag-ingestion/documents",
        files=_pdf_file(filename="policy.pdf", content=f"%PDF-1.4 version one {run_id}".encode()),
    )
    second = client.post(
        "/v1/rag-ingestion/documents",
        files=_pdf_file(filename="policy.pdf", content=f"%PDF-1.4 version two {run_id}".encode()),
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
        "/v1/rag-ingestion/documents", files=files, data={"supersedes_document_id": "some-id"}
    )

    assert response.status_code == 422


def test_supersedes_document_id_pointing_at_an_unknown_document_is_rejected():
    response = client.post(
        "/v1/rag-ingestion/documents",
        files=_pdf_file(),
        data={"supersedes_document_id": "does-not-exist"},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "rejected"
    assert "does-not-exist" in result["error"]
    assert result["error_code"] == "SUPERSEDES_TARGET_NOT_FOUND"


def test_supersedes_document_id_on_a_valid_target_is_recorded_on_the_new_document():
    target_response = client.post("/v1/rag-ingestion/documents", files=_pdf_file(filename="v1.pdf"))
    target_id = target_response.json()["results"][0]["document_id"]

    response = client.post(
        "/v1/rag-ingestion/documents",
        files=_pdf_file(filename="v2.pdf"),
        data={"supersedes_document_id": target_id},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "uploaded"
    new_document_id = result["document_id"]

    # supersedes is recorded now, but the old document isn't flipped to
    # is_current=false until the new one is actually indexed (not yet here).
    new_document = client.get(f"/v1/rag-ingestion/documents/{new_document_id}").json()
    assert new_document["supersedes"] == target_id
    assert new_document["is_current"] is True

    target_document = client.get(f"/v1/rag-ingestion/documents/{target_id}").json()
    assert target_document["is_current"] is True
    assert target_document["superseded_by"] is None
