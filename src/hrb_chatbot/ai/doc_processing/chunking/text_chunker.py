"""Extracts a PDF's text and splits it into overlapping chunks.

Workshop Module 2's "recursive" chunking strategy, written natively (no
langchain-text-splitters) so every step is visible in one small file rather
than behind a library call: try the largest separator first (paragraph
breaks), and only fall back to a smaller one (sentences, then plain
characters) for a piece that's still too big after that split. Once every
piece is small enough, small neighbouring pieces are packed back together
up to chunk_size, carrying the tail of one chunk into the start of the next
(the overlap) so a sentence split across a chunk boundary isn't lost to
whichever chunk it landed in.
"""

from pypdf import PdfReader

from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.chunking")

# 1000 characters is a few short paragraphs - small enough that a single
# chunk stays topically focused, large enough that most benefits-document
# answers don't get split across a chunk boundary. 150 characters of overlap
# is roughly a sentence or two - enough that a sentence split right at a
# chunk boundary still appears whole in at least one of the two chunks.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

# Tried in order, largest structural unit first. The last, empty-string
# entry means "no separator helps any more - cut at a fixed character
# count", which only fires for unusually long unbroken runs of text.
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def extract_text_from_pdf(file_path: str) -> str:
    """Return every page's text, joined with a blank line between pages."""
    reader = PdfReader(file_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages_text)


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Split text into pieces no larger than chunk_size, preferring the
    largest separator that actually gets every piece under the limit."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separator, *remaining_separators = separators

    if separator == "":
        # Last resort: no separator left that helps - hard-cut at chunk_size.
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    pieces = text.split(separator)

    result = []
    for piece in pieces:
        if len(piece) <= chunk_size:
            if piece.strip():
                result.append(piece)
        else:
            # This piece is still too big even at this separator - recurse
            # with the next, smaller one.
            result.extend(_recursive_split(piece, remaining_separators, chunk_size))
    return result


def _merge_with_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Greedily pack small pieces up to chunk_size, carrying overlap forward."""
    chunks = []
    current = ""

    for piece in pieces:
        candidate = f"{current} {piece}".strip() if current else piece

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        # Start the next chunk with the tail of the one just finished, so
        # content right at the boundary isn't only ever seen in one chunk.
        overlap_text = current[-chunk_overlap:] if current else ""
        current = f"{overlap_text} {piece}".strip() if overlap_text else piece

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
