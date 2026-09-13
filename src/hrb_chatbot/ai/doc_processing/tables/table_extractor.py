"""Table-aware PDF parsing, separate from text_chunker.py's plain-text
extraction (pypdf's page.extract_text() has no table awareness at all - cells
get flattened into reading-order text, usually losing row/column structure).
Uses pdfplumber, which understands table geometry directly.
"""

import pdfplumber

from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.tables")


def extract_tables_from_pdf(file_path: str) -> list[str]:
    """Return one formatted markdown-table string per table found, in
    document order. Never raises - a page pdfplumber can't parse is logged
    and skipped, not fatal to the rest of extraction."""
    tables_as_text = []

    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            try:
                page_tables = page.extract_tables()
            except Exception as error:
                logger.warning("Table extraction failed on page %d: %s: %s", page_number, type(error).__name__, error)
                continue

            for table in page_tables:
                formatted = _format_table_as_markdown(table)
                if formatted:
                    tables_as_text.append(formatted)

    logger.info("Extracted %d table(s) from %s", len(tables_as_text), file_path)
    return tables_as_text


def _format_table_as_markdown(table: list[list[str | None]]) -> str | None:
    """Turn pdfplumber's row/cell grid into a markdown table - a shape
    embedding models handle far better than a flattened wall of numbers,
    and one a human reading a chunk can still recognize as a table."""
    rows = [row for row in table if any(cell not in (None, "") for cell in row)]
    if not rows:
        return None

    def clean_row(row: list[str | None]) -> list[str]:
        return [(cell or "").replace("\n", " ").strip() for cell in row]

    header, *body_rows = [clean_row(row) for row in rows]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in body_rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)
