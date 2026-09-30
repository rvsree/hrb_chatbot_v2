"""LLM-based extraction of document-level metadata - best-effort, never blocks indexing on a bad guess."""

import json

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.metadata_extraction")

# Most fields are on a document's first page - no need to pay for tokens sending the whole doc.
MAX_CHARACTERS_SENT = int(read_setting(None, "METADATA_EXTRACTION_MAX_CHARACTERS", 3000))

# author/doc_date/doc_version often live in a closing colophon, past the head excerpt above.
TAIL_CHARACTERS_SENT = int(read_setting(None, "METADATA_EXTRACTION_TAIL_CHARACTERS", 1000))

EMPTY_RESULT = {
    "owner": None,
    "department": None,
    "doc_category": None,
    "purpose": None,
    "doc_description": None,
    "effective_date": None,
    "audience": None,
    "confidentiality_level": None,
    "author": None,
    "doc_date": None,
    "doc_version": None,
}

EXTRACTION_QUESTION = (
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


def extract_document_metadata(text: str) -> dict:
    """Return EMPTY_RESULT's 11 keys filled in where possible - never raises."""
    if not text.strip():
        return dict(EMPTY_RESULT)

    head = text[:MAX_CHARACTERS_SENT]
    tail = text[-TAIL_CHARACTERS_SENT:] if len(text) > MAX_CHARACTERS_SENT + TAIL_CHARACTERS_SENT else ""
    excerpt = f"{head}\n\n...\n\n{tail}" if tail else head

    try:
        chat_client = get_client_gateway().openai_chat()
        response = chat_client.ask(EXTRACTION_QUESTION, context=excerpt, temperature=0.0)
        extracted = _parse_json_object(response)
    except Exception as error:
        logger.warning("Document metadata extraction failed: %s: %s", type(error).__name__, error)
        return dict(EMPTY_RESULT)

    result = dict(EMPTY_RESULT)
    for key in result:
        value = extracted.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def _parse_json_object(response: str) -> dict:
    """Pulls out the outermost {...} - models sometimes wrap JSON in prose/a code fence despite instructions."""
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    return json.loads(response[start : end + 1])
