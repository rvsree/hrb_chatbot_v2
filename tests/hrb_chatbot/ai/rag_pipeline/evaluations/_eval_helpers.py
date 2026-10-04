"""Shared helper for the agentic-rag eval adapters (Phase 71) - was duplicated
identically in test_single_agentic_rag_golden_dataset.py and
test_multi_agentic_rag_golden_dataset.py."""

import re

# The exact header search_knowledge_base() already writes - reusing that real
# structure to recover source filenames, not inventing a new id scheme.
_SOURCE_FILENAME_PATTERN = re.compile(r"--- Source \d+ \(([^)]+)\) ---")


def extract_filenames(texts: list[str]) -> list[str]:
    filenames = []
    for text in texts:
        filenames.extend(_SOURCE_FILENAME_PATTERN.findall(text))
    return filenames
