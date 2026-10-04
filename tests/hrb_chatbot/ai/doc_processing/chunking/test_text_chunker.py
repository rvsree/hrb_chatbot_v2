"""Tests for chunk_text() and its strategy functions
(ai/doc_processing/chunking/text_chunker.py). Cases are selective, covering
the behaviors most worth protecting against regression, not every possible
input. No mocking needed for fixed/recursive/markdown/html/none - they're
pure logic (string in, list of strings out), backed by LangChain's own
splitters. "semantic" needs a real embedding call, so it's not covered here
- same reasoning this project already applies elsewhere for not spending
real API cost inside pytest."""

from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import (
    DEFAULT_CHUNK_SIZE,
    LARGE_DOCUMENT_CHUNK_SIZE,
    LARGE_DOCUMENT_MIN_LENGTH,
    chunk_fixed,
    chunk_html,
    chunk_markdown,
    chunk_none,
    chunk_recursive,
    chunk_text,
    decide_chunk_size,
    decide_chunking_strategy,
)


def test_text_shorter_than_chunk_size_returns_one_chunk():
    text = "This is a short paragraph, well under the chunk size limit."
    chunks = chunk_recursive(text, chunk_size=1000, chunk_overlap=150)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text_returns_no_chunks():
    assert chunk_recursive("", chunk_size=1000, chunk_overlap=150) == []
    assert chunk_none("") == []
    assert chunk_none("   ") == []


def test_long_text_is_split_into_multiple_chunks_each_within_the_limit():
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40  # roughly 2,400 characters

    chunks = chunk_recursive(text, chunk_size=500, chunk_overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        # Some slack allowed - LangChain's splitter can go slightly over
        # chunk_size when a single separator-delimited piece is close to the limit.
        assert len(chunk) <= 600


def test_consecutive_chunks_share_overlapping_text_when_overlap_is_set():
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40

    chunks = chunk_recursive(text, chunk_size=500, chunk_overlap=100)
    assert len(chunks) >= 2

    # Overlap means the tail of one chunk should reappear at the start of
    # the next; checking the last 20 chars is looser than an exact-offset
    # match since LangChain's splitter trims whitespace at the join.
    tail_of_first_chunk = chunks[0][-20:].strip()
    assert tail_of_first_chunk in chunks[1]


def test_zero_overlap_means_no_shared_text_between_chunks():
    # Every word is unique (word0, word1, word2, ...) with no repeated
    # phrase anywhere - unlike a repeated sentence, this means a tail
    # substring can only reappear in the next chunk if overlap actually
    # copied it there, not by coincidence.
    text = " ".join(f"word{i}" for i in range(300))

    chunks = chunk_recursive(text, chunk_size=500, chunk_overlap=0)
    assert len(chunks) >= 2

    tail_of_first_chunk = chunks[0][-25:].strip()
    assert tail_of_first_chunk not in chunks[1]


def test_chunk_fixed_splits_on_the_single_separator():
    text = "line one\nline two\nline three\nline four"
    chunks = chunk_fixed(text, chunk_size=15, chunk_overlap=0)

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)


def test_chunk_none_returns_the_whole_document_as_one_chunk():
    text = "Some content that would normally be split, but isn't here."
    assert chunk_none(text) == [text]


def test_chunk_markdown_splits_on_headers():
    text = "# Section One\nFirst section text.\n\n## Section Two\nSecond section text."
    chunks = chunk_markdown(text)

    assert len(chunks) == 2
    assert "First section text" in chunks[0]
    assert "Second section text" in chunks[1]


def test_chunk_html_splits_on_header_tags():
    text = "<h1>Title</h1><p>Intro text.</p><h2>Sub</h2><p>Sub text.</p>"
    chunks = chunk_html(text)

    assert len(chunks) >= 1
    assert any("Intro text" in chunk for chunk in chunks)


def test_decide_chunking_strategy_picks_markdown_for_markdown_headers():
    text = "# A Heading\n\nSome body text under it."
    assert decide_chunking_strategy(text) == "markdown"


def test_decide_chunking_strategy_picks_html_for_html_headers():
    text = "<h1>A Heading</h1><p>Some body text under it.</p>"
    assert decide_chunking_strategy(text) == "html"


def test_decide_chunking_strategy_picks_none_for_short_plain_text():
    text = "Just a short ticket description, nowhere near chunk_size."
    assert decide_chunking_strategy(text) == "none"


def test_decide_chunking_strategy_picks_recursive_for_long_plain_text():
    text = "This is one sentence about JPMorgan Chase benefits policy. " * 40
    assert decide_chunking_strategy(text) == "recursive"


def test_chunk_text_uses_explicit_strategy_when_given():
    text = "# A Heading\n\nSome body text under it."
    # Explicitly ask for "none" even though auto-selection would pick "markdown".
    chunks = chunk_text(text, chunking_strategy="none")
    assert chunks == [text]


def test_chunk_text_auto_selects_when_no_strategy_given():
    text = "# A Heading\n\nSome body text under it."
    chunks = chunk_text(text)
    # Auto-selected "markdown" here, which splits into one chunk per header.
    assert len(chunks) == 1
    assert "Some body text under it" in chunks[0]


def test_chunk_text_rejects_an_unknown_strategy():
    try:
        chunk_text("some text", chunking_strategy="not-a-real-strategy")
        assert False, "expected a ValueError"
    except ValueError as error:
        assert "not-a-real-strategy" in str(error)


def test_decide_chunk_size_defaults_when_no_signal_applies():
    text = "This is one sentence about JPMorgan Chase benefits policy. " * 40
    assert decide_chunk_size(text) == DEFAULT_CHUNK_SIZE


def test_decide_chunk_size_ignores_table_size_entirely():
    # Phase 75 - a huge table no longer inflates chunk_size at all, since
    # tables are pulled out and kept whole before any size-based splitting happens.
    table_content = "a" * 5000
    text = f"Some intro text.\n\n[TABLE]{table_content}[/TABLE]"

    assert decide_chunk_size(text) == DEFAULT_CHUNK_SIZE


def test_decide_chunk_size_grows_for_a_long_document():
    text = "word " * (LARGE_DOCUMENT_MIN_LENGTH // 4)  # comfortably over the threshold
    assert decide_chunk_size(text) == LARGE_DOCUMENT_CHUNK_SIZE


def test_chunk_text_keeps_a_table_block_whole_even_when_it_exceeds_chunk_size():
    # Phase 75 - a table far bigger than chunk_size still comes back as one
    # unbroken chunk, never split across two.
    table_content = "c" * 5000
    text = f"Some intro text.\n\n[TABLE]\n{table_content}\n[/TABLE]"

    chunks = chunk_text(text, chunking_strategy="recursive", chunk_size=500, chunk_overlap=50)

    table_chunks = [chunk for chunk in chunks if table_content in chunk]
    assert len(table_chunks) == 1
    assert table_chunks[0].count("[TABLE]") == 1
    assert table_chunks[0].count("[/TABLE]") == 1


def test_chunk_text_handles_multiple_tables_as_separate_whole_chunks():
    text = "Intro text.\n\n[TABLE]\nfirst table\n[/TABLE]\n\nMore text.\n\n[TABLE]\nsecond table\n[/TABLE]"

    chunks = chunk_text(text, chunking_strategy="recursive", chunk_size=500, chunk_overlap=50)

    table_chunks = [chunk for chunk in chunks if "[TABLE]" in chunk]
    assert len(table_chunks) == 2
    assert any("first table" in chunk for chunk in table_chunks)
    assert any("second table" in chunk for chunk in table_chunks)


def test_chunk_text_with_no_tables_behaves_exactly_as_before():
    text = "This is one sentence about JPMorgan Chase benefits policy. " * 40
    chunks = chunk_text(text, chunking_strategy="recursive", chunk_size=500, chunk_overlap=50)

    assert len(chunks) > 1
    assert not any("[TABLE]" in chunk for chunk in chunks)
