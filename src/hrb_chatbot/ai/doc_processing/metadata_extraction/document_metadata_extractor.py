"""LLM-based extraction of document-level metadata (owner, department, doc
type, purpose) from a document's own text - none of this is provided by the
uploader, so the only way to get it is to ask a model to read the document
and guess, same as a human skimming the first page would.

Best-effort by design: a wrong or missing guess here must never block
indexing - see extract_document_metadata()'s own try/except.
"""

import json

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.metadata_extraction")

# Owner/department/type/purpose is almost always stated (or inferable) on a
# document's first page/header - no need to send the whole document and pay
# for tokens a title page already answers.
MAX_CHARACTERS_SENT = 3000

EMPTY_RESULT = {"owner": None, "department": None, "doc_type": None, "purpose": None}

EXTRACTION_QUESTION = (
    "Read the document text above and answer with ONLY a JSON object, no other "
    "text, in exactly this shape:\n"
    '{"owner": "<person or role who owns this document, or null>", '
    '"department": "<department/team, or null>", '
    '"doc_type": "<one of: policy, regulatory, investment, benefits, other>", '
    '"purpose": "<one sentence describing the document\'s scope/purpose, or null>"}\n'
    "Use null (not a guess) for any field the text doesn't actually support."
)


def extract_document_metadata(text: str) -> dict:
    """Return {"owner", "department", "doc_type", "purpose"} - any value may
    be None if the model couldn't determine it, or if extraction failed
    outright. Never raises."""
    if not text.strip():
        return dict(EMPTY_RESULT)

    excerpt = text[:MAX_CHARACTERS_SENT]

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
    """Models sometimes wrap JSON in prose or a markdown code fence despite
    being told not to - pull out the outermost {...} rather than assuming
    the whole response is clean JSON."""
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    return json.loads(response[start : end + 1])
