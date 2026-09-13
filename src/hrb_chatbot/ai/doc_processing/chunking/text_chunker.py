"""Extracts a PDF's text and splits it into overlapping chunks.

Recursive splitting: try the largest separator first (paragraph breaks),
falling back to smaller ones (sentences, then characters) only for pieces
still too big. Small pieces are then packed back together up to chunk_size,
carrying overlap forward so a boundary split doesn't lose content.
"""

from pypdf import PdfReader

from src.hrb_chatbot.ai.doc_processing.tables.table_extractor import extract_tables_from_pdf
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.chunking")

# 1000 chars keeps a chunk topically focused; 150 char overlap is roughly a
# sentence, enough that a boundary-split sentence still appears whole somewhere.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

# Largest structural unit first; trailing "" means "hard-cut at chunk_size".
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


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


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Split text into pieces no larger than chunk_size, preferring the
    largest separator that actually gets every piece under the limit."""
    if len(text) <= chunk_size:
        if text.strip():
            return [text]
        else:
            return []

    separator = separators[0]
    remaining_separators = separators[1:]

    if separator == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    pieces = text.split(separator)

    result = []
    for piece in pieces:
        if len(piece) <= chunk_size:
            if piece.strip():
                result.append(piece)
        else:
            # Still too big at this separator - recurse with the next, smaller one.
            result.extend(_recursive_split(piece, remaining_separators, chunk_size))
    return result


def _merge_with_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Greedily pack small pieces up to chunk_size, carrying overlap forward."""
    chunks = []
    current = ""

    for piece in pieces:
        if current:
            candidate = f"{current} {piece}".strip()
        else:
            candidate = piece

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        # Carry the tail of the finished chunk forward so boundary content
        # isn't only ever seen in one chunk.
        if current:
            overlap_text = current[-chunk_overlap:]
        else:
            overlap_text = ""

        if overlap_text:
            current = f"{overlap_text} {piece}".strip()
        else:
            current = piece

    if current:
        chunks.append(current)

    return chunks


def chunk_text(
    text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping chunks ready to embed."""
    pieces = _recursive_split(text.strip(), SEPARATORS, chunk_size)
    chunks = _merge_with_overlap(pieces, chunk_size, chunk_overlap)
    logger.info("Split %d characters of text into %d chunks", len(text), len(chunks))
    return chunks
