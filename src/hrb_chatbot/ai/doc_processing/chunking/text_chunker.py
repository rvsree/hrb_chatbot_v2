"""Extracts PDF text and splits it into chunks via LangChain's own splitters
(workshop Module 2) - six plain functions, one per technique, no classes."""

import re

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
DEFAULT_CHUNK_SIZE = int(read_setting(None, "CHUNK_DEFAULT_SIZE", 1000))
DEFAULT_CHUNK_OVERLAP = int(read_setting(None, "CHUNK_DEFAULT_OVERLAP", 150))

# Below this length, a document fits in one chunk anyway - matches the "not
# critical for short tickets/documents" takeaway from workshop Module 1.
WHOLE_DOCUMENT_MAX_LENGTH = DEFAULT_CHUNK_SIZE

# table_extractor.py appends tables as [TABLE]...[/TABLE] blocks - matched
# here so decide_chunk_size() can keep one whole in one chunk.
TABLE_BLOCK_PATTERN = re.compile(r"\[TABLE\](.*?)\[/TABLE\]", re.DOTALL)

# Above this length, a document would fragment into 10+ tiny chunks at the
# default size, each losing surrounding context - use a larger chunk size instead.
LARGE_DOCUMENT_MIN_LENGTH = int(read_setting(None, "CHUNK_LARGE_DOCUMENT_MIN_LENGTH", 10_000))
LARGE_DOCUMENT_CHUNK_SIZE = int(read_setting(None, "CHUNK_LARGE_DOCUMENT_CHUNK_SIZE", 1500))


def extract_text_from_pdf(file_path: str) -> str:
    """Return every page's text plus any tables (via pdfplumber -
    table_extractor.py, since pypdf has no table awareness) appended as
    their own markdown blocks after the page text, not inlined in place."""
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


# Every strategy a caller can pass explicitly, mapped to its function -
# "semantic" is explicit-only (see decide_chunking_strategy), never auto-selected.
CHUNKING_STRATEGIES = {
    "fixed": chunk_fixed,
    "recursive": chunk_recursive,
    "semantic": chunk_semantic,
    "markdown": chunk_markdown,
    "html": chunk_html,
    "none": chunk_none,
}


def decide_chunking_strategy(text: str) -> str:
    """Auto-pick a strategy when none was given - rules from the workshop's
    own Decision Matrix, not invented thresholds. "semantic" stays explicit-
    only (its "accuracy critical" trigger isn't detectable from text alone)."""
    stripped = text.strip()

    # A line is a markdown heading only if "#" starts it after stripping
    # leading whitespace - an incidental "#" mid-sentence doesn't count.
    heading_lines = [line for line in stripped.splitlines() if line.strip().startswith("#")]
    if heading_lines:
        logger.info(
            "chunking: auto-select rationale - %d markdown heading line(s) found -> 'markdown'",
            len(heading_lines),
        )
        return "markdown"

    lowered = stripped.lower()
    html_heading_tags_found = [tag for tag in ("<h1", "<h2", "<h3") if tag in lowered]
    if html_heading_tags_found:
        logger.info(
            "chunking: auto-select rationale - HTML heading tag(s) %s found -> 'html'",
            html_heading_tags_found,
        )
        return "html"

    character_count = len(stripped)
    if character_count <= WHOLE_DOCUMENT_MAX_LENGTH:
        logger.info(
            "chunking: auto-select rationale - %d character(s), at or under the %d-character "
            "whole-document threshold -> 'none'",
            character_count,
            WHOLE_DOCUMENT_MAX_LENGTH,
        )
        return "none"

    logger.info(
        "chunking: auto-select rationale - %d character(s), no markdown/HTML heading structure "
        "found, over the %d-character whole-document threshold -> 'recursive' (default)",
        character_count,
        WHOLE_DOCUMENT_MAX_LENGTH,
    )
    return "recursive"


def decide_chunk_size(text: str) -> int:
    """Auto-pick a chunk size when none was given - same "content decides,
    not a hardcoded guess" idea as decide_chunking_strategy(). Only grows
    past the default, never shrinks it - takes the max of both signals."""
    stripped = text.strip()

    table_lengths = [len(block) for block in TABLE_BLOCK_PATTERN.findall(stripped)]
    largest_table_length = max(table_lengths, default=0)

    candidates = [DEFAULT_CHUNK_SIZE]
    if len(stripped) > LARGE_DOCUMENT_MIN_LENGTH:
        candidates.append(LARGE_DOCUMENT_CHUNK_SIZE)
    if largest_table_length > DEFAULT_CHUNK_SIZE:
        # Big enough that the splitter never recurses into this block.
        candidates.append(largest_table_length + DEFAULT_CHUNK_OVERLAP)

    chunk_size = max(candidates)
    if chunk_size != DEFAULT_CHUNK_SIZE:
        logger.info(
            "chunk_size: auto-select rationale - %d character(s), largest [TABLE] block=%d "
            "character(s) -> %d (default is %d)",
            len(stripped),
            largest_table_length,
            chunk_size,
            DEFAULT_CHUNK_SIZE,
        )
    return chunk_size


def chunk_text(
    text: str,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into chunks ready to embed, using the given strategy/
    chunk_size - or, if not given, auto-selecting both (see
    decide_chunking_strategy/decide_chunk_size)."""
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
        resolved_chunk_size = chunk_size if chunk_size is not None else decide_chunk_size(text)
        chunks = chunk_function(text, chunk_size=resolved_chunk_size, chunk_overlap=chunk_overlap)
    else:
        chunks = chunk_function(text)

    logger.info("Split %d characters of text into %d chunks (strategy=%s)", len(text), len(chunks), strategy)
    return chunks
