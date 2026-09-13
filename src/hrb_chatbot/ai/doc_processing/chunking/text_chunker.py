"""Extracts a PDF's text and splits it into chunks, using LangChain's own
text splitters directly (workshop Module 2) instead of a hand-written one.

Six plain functions, one per technique - no classes/interfaces, mirroring
how the workshop's own demo.py is written. Each takes text (and chunk_size/
chunk_overlap where that applies) and returns a list of chunk strings.
"""

from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import (
    CharacterTextSplitter,
    HTMLHeaderTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pypdf import PdfReader

from src.hrb_chatbot.ai.doc_processing.tables.table_extractor import extract_tables_from_pdf
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.chunking")

# 1000 chars keeps a chunk topically focused; 150 char overlap is roughly a
# sentence, enough that a boundary-split sentence still appears whole somewhere.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

# Below this length, a document fits in one chunk anyway - matches the "not
# critical for short tickets/documents" takeaway from workshop Module 1.
WHOLE_DOCUMENT_MAX_LENGTH = DEFAULT_CHUNK_SIZE


def extract_text_from_pdf(file_path: str) -> str:
    """Return every page's plain text, plus any tables (extracted separately
    via pdfplumber - see ai/doc_processing/tables/table_extractor.py, since
    pypdf's extract_text() has no table awareness) appended as their own
    markdown-formatted blocks. Tables are appended after all page text
    rather than inlined at their exact original position - reconstructing
    precise layout position isn't needed for chunking/embedding, only
    keeping the table's row/column structure readable is."""
    reader = PdfReader(file_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text)

    tables = extract_tables_from_pdf(file_path)
    if tables:
        tables_section = "\n\n".join(f"[TABLE]\n{table}\n[/TABLE]" for table in tables)
        text = f"{text}\n\n{tables_section}"

    return text


def chunk_fixed(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    # Splits on a single separator only ("\n") - simple and fast, but may cut
    # a sentence in half. Good for quick prototypes, not the default.
    splitter = CharacterTextSplitter(separator="\n", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def chunk_recursive(
    text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    # Tries paragraph, then line, then sentence breaks before falling back to
    # a hard cut - the workshop's own "recommended default" for general text.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    return splitter.split_text(text)


def chunk_semantic(text: str) -> list[str]:
    # Embeds each sentence and splits where meaning shifts, not at a fixed
    # size - higher quality, but costs one embedding call per sentence.
    api_key = read_setting(None, "OPENAI_API_KEY")
    base_url = read_url_setting(None, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    embedding_model = read_setting(None, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
    embeddings = OpenAIEmbeddings(api_key=api_key, base_url=base_url, model=embedding_model)
    splitter = SemanticChunker(embeddings, breakpoint_threshold_type="standard_deviation")
    return splitter.split_text(text)


def chunk_markdown(text: str) -> list[str]:
    # Splits on markdown headers (#, ##, ###) so each chunk stays under one
    # heading - for documentation/wikis, not plain PDF-extracted text.
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    )
    documents = splitter.split_text(text)
    return [document.page_content for document in documents if document.page_content.strip()]


def chunk_html(text: str) -> list[str]:
    # Same idea as chunk_markdown, but for <h1>/<h2>/<h3> tags instead.
    splitter = HTMLHeaderTextSplitter(headers_to_split_on=[("h1", "Header 1"), ("h2", "Header 2"), ("h3", "Header 3")])
    documents = splitter.split_text(text)
    return [document.page_content for document in documents if document.page_content.strip()]


def chunk_none(text: str) -> list[str]:
    # No splitting at all - the whole document is one chunk. Fine for short
    # content where a boundary split would only lose context for no benefit.
    stripped = text.strip()
    return [stripped] if stripped else []


# Every strategy name a caller can pass explicitly, mapped to its function.
# "semantic" is never auto-selected (see decide_chunking_strategy below) but
# is still selectable here by an explicit chunking_strategy request field.
CHUNKING_STRATEGIES = {
    "fixed": chunk_fixed,
    "recursive": chunk_recursive,
    "semantic": chunk_semantic,
    "markdown": chunk_markdown,
    "html": chunk_html,
    "none": chunk_none,
}


def decide_chunking_strategy(text: str) -> str:
    """Auto-pick a strategy when the caller didn't say which one to use.
    Rules sourced directly from the workshop's own decision guidance
    (modules/2_chunking/notes.md's Decision Matrix, and Module 1's "not
    critical for short tickets" takeaway) - not invented thresholds.
    "semantic" is deliberately never auto-selected here: the workshop ties
    it to "when accuracy is critical," which isn't detectable from the text
    alone, so it stays an explicit-only choice."""
    if "#" in text and any(line.strip().startswith("#") for line in text.splitlines()):
        return "markdown"
    if "<h1" in text.lower() or "<h2" in text.lower() or "<h3" in text.lower():
        return "html"
    if len(text.strip()) <= WHOLE_DOCUMENT_MAX_LENGTH:
        return "none"
    return "recursive"


def chunk_text(
    text: str,
    chunking_strategy: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into chunks ready to embed, using the given strategy - or,
    if none was given, auto-selecting one (see decide_chunking_strategy)."""
    if chunking_strategy:
        strategy = chunking_strategy
        logger.info("chunking: explicit strategy=%s", strategy)
    else:
        strategy = decide_chunking_strategy(text)
        logger.info("chunking: auto-selected strategy=%s", strategy)

    if strategy not in CHUNKING_STRATEGIES:
        raise ValueError(f"Unknown chunking_strategy {strategy!r} - choose one of {list(CHUNKING_STRATEGIES)}")

    chunk_function = CHUNKING_STRATEGIES[strategy]
    if strategy in ("fixed", "recursive"):
        chunks = chunk_function(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    else:
        chunks = chunk_function(text)

    logger.info("Split %d characters of text into %d chunks (strategy=%s)", len(text), len(chunks), strategy)
    return chunks
