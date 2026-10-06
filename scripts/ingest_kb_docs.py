#!/usr/bin/env python
"""Uploads and indexes every real KB PDF (resources/kb_docs/) against a
running local server - used by the release-gate CI workflow (Phase 80) to
populate a fresh runner's empty vector store before scoring. Goes through
the real POST /hrb-chatbot/v1/genai-rag/ingest-document/documents endpoint, not a
shortcut that calls internal functions directly, so the gate tests what a
real deploy would actually serve. Safe to re-run - the endpoint's own
content-hash dedup (Phase 16) makes a second run against an
already-populated KB a no-op, not a duplicate-document error."""

import glob
import json
import os
import sys

import requests

BASE_URL = os.environ.get("RELEASE_GATE_BASE_URL", "http://127.0.0.1:8093")
HR_SUPPORT_USER_PROFILE = {"employee_id": "CI-RELEASE-GATE", "full_name": "Release Gate", "role": "hr_support"}


def main() -> int:
    pdf_paths = sorted(glob.glob("resources/kb_docs/*.pdf"))
    if not pdf_paths:
        print("No KB PDFs found under resources/kb_docs/ - nothing to ingest.")
        return 1

    print(f"Ingesting {len(pdf_paths)} KB document(s) from {BASE_URL}...")

    open_files = [open(path, "rb") for path in pdf_paths]
    try:
        files = [("files", (os.path.basename(path), handle, "application/pdf")) for path, handle in zip(pdf_paths, open_files, strict=True)]
        payload = {"payload": json.dumps({"user_profile": HR_SUPPORT_USER_PROFILE})}

        response = requests.post(
            f"{BASE_URL}/hrb-chatbot/v1/genai-rag/ingest-document/documents", files=files, data=payload, timeout=300
        )
    finally:
        for handle in open_files:
            handle.close()

    if response.status_code != 200:
        print(f"Ingestion failed: {response.status_code} {response.text}")
        return 1

    for result in response.json()["results"]:
        print(f"  {result['filename']}: {result['status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
