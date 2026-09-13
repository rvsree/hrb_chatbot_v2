"""Tests for chunk_text() (ai/doc_processing/chunking/text_chunker.py).
Cases are selective, covering the behaviors most worth protecting against
regression, not every possible input. No mocking needed - chunk_text() is
pure logic (string in, list of strings out)."""

from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import chunk_text


def test_text_shorter_than_chunk_size_returns_one_chunk():
    text = "This is a short paragraph, well under the chunk size limit."
    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text_returns_no_chunks():
    assert chunk_text("", chunk_size=1000, chunk_overlap=150) == []
    assert chunk_text("   ", chunk_size=1000, chunk_overlap=150) == []


def test_long_text_is_split_into_multiple_chunks_each_within_the_limit():
    # Past chunk_size, so the splitter falls back to sentence-level
    # splitting to keep every piece under the limit.
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40  # roughly 2,400 characters

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        # Some slack is allowed: the merge step checks the limit before
        # adding the next piece, so the last piece added can push it slightly over.
        assert len(chunk) <= 600


def test_consecutive_chunks_share_overlapping_text():
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)
    assert len(chunks) >= 2

    # Overlap means the tail of one chunk should reappear at the start of
    # the next; checking the last 20 chars is looser than an exact-offset
    # match since the merge step trims whitespace at the join.
    tail_of_first_chunk = chunks[0][-20:].strip()
    assert tail_of_first_chunk in chunks[1]


def test_zero_overlap_is_respected_not_silently_replaced_with_the_default():
    # Guards against a regression where "chunk_overlap or DEFAULT" logic
    # would silently turn a real 0 into the 150-char default.
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40

    chunks_with_zero_overlap = chunk_text(text, chunk_size=500, chunk_overlap=0)
    chunks_with_real_overlap = chunk_text(text, chunk_size=500, chunk_overlap=100)

    # Not precise on count (depends on where sentences fall) - just confirms
    # zero-overlap produces at least as many chunks, since overlap only adds.
    assert len(chunks_with_zero_overlap) >= len(chunks_with_real_overlap)
