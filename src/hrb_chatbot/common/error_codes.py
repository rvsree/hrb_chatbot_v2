"""Stable, machine-readable error codes - every json_error() call site names
one. The human-readable message can change wording freely; the code is the
part a caller (a script, a future agent's tool-calling retry logic) should
actually branch on, instead of string-matching message text.
"""

VALIDATION_ERROR = "VALIDATION_ERROR"
DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
RATE_LIMITED = "RATE_LIMITED"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
INDEXING_FAILED = "INDEXING_FAILED"
QUERY_FAILED = "QUERY_FAILED"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
INTERNAL_ERROR = "INTERNAL_ERROR"

# Per-file upload rejection reasons - not HTTP error responses (a rejected
# file is still a 200, see DocumentUploadResult.status), but the same
# "give the caller something to branch on, not just prose" reasoning
# applies to a batch-uploading caller deciding which files to retry.
INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
EMPTY_FILE = "EMPTY_FILE"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
UPLOAD_READ_FAILED = "UPLOAD_READ_FAILED"
SUPERSEDES_TARGET_NOT_FOUND = "SUPERSEDES_TARGET_NOT_FOUND"
STORAGE_FAILURE = "STORAGE_FAILURE"
