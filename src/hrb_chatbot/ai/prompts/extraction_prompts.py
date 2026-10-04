"""Prompt patterns for pulling structured data out of a document - document-level
metadata, and document-level entities. Static prompts are module-level constants;
a prompt needing per-call values is a function returning a string. No templating
library - plain Python, matching this project's existing convention."""

# Migrated verbatim from document_metadata_extractor.py (Phase 63) - same string,
# same behavior, now in one reusable place instead of inline in the one function
# that used it.
DOCUMENT_METADATA_EXTRACTION_PROMPT = (
    "Read the document text above and answer with ONLY a JSON object, no other "
    "text, in exactly this shape:\n"
    '{"owner": "<person or role who owns this document, or null>", '
    '"department": "<department/team, or null>", '
    '"doc_category": "<one of: policy, regulatory, investment, benefits, other>", '
    '"purpose": "<one sentence describing the document\'s scope/purpose, or null>", '
    '"doc_description": "<the specific topic this document covers, in the '
    "document's own terms, e.g. '401k', 'health benefits', 'leave policy' - "
    'not a fixed list, or null>", '
    '"effective_date": "<when the document says it takes effect, in its own '
    'words, or null>", '
    '"audience": "<which employee group this document applies to, or null>", '
    '"confidentiality_level": "<the document\'s own stated sensitivity, e.g. '
    '\'Internal\'/\'Confidential\', or null>", '
    '"author": "<the person or organization credited as the document\'s '
    'author, or null>", '
    '"doc_date": "<the document\'s own stated creation/publish date, '
    "distinct from effective_date, or null>\", "
    '"doc_version": "<the document\'s own stated version, e.g. \'1.0\', '
    'or null>"}\n'
    "Use null (not a guess) for any field the text doesn't actually support."
)


def build_entity_extraction_prompt(text: str) -> str:
    """Example template (Phase 63) - pulls named entities an HR document ingestion
    use case might need, not document-level metadata. Never asks for a full SSN or
    account number, only whether one is present - matches this project's existing
    PII-masking stance (Phase 7's NeMo Guardrails config), not a new policy."""
    if not text or not text.strip():
        raise ValueError("build_entity_extraction_prompt requires non-empty text")

    return (
        "Read the document text below and answer with ONLY a JSON object, no "
        "other text, in exactly this shape:\n"
        '{"employee_names": ["<full name as written in the document>", ...], '
        '"department": "<department/team mentioned, or null>", '
        '"plan_or_enrollment_type": "<e.g. \'health\', \'401k\', \'dental\', '
        'or null>", '
        '"dates_mentioned": ["<any date exactly as written in the document>", ...], '
        '"dollar_amounts_mentioned": ["<any dollar amount exactly as written, '
        'e.g. \'$450.00\'>", ...], '
        '"policy_or_plan_numbers": ["<any policy/plan/account identifier as '
        'written>", ...], '
        '"contains_full_ssn": <true or false - do NOT output the SSN itself, '
        "only whether one appears>, "
        '"contains_full_account_number": <true or false - same rule, never '
        "output the number itself>}\n"
        "Use an empty list, not a guess, for anything the text doesn't actually "
        "support.\n\n"
        f"DOCUMENT TEXT:\n{text}"
    )
