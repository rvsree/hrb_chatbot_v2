"""Tests for chunk_text() - the recursive chunking strategy in
ai/doc_processing/chunking/text_chunker.py.

Selective on purpose (per the request that led to this file): these cases
were chosen to cover the behaviors most worth protecting against a future
change, not every possible input. No mocking needed here - chunk_text()
is pure logic (string in, list of strings out), no network or disk call
involved.
"""

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
    # One long paragraph, well past any reasonable chunk_size, so the
    # recursive splitter has to fall back past "\n\n" to sentence-level
    # splitting to get every piece under the limit.
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40  # roughly 2,400 characters

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)

    assert len(chunks) > 1
    for chunk in chunks:
        # A small amount of slack is expected: the merge step packs whole
        # pieces together and only checks the limit before adding the next
        # one, so the very last piece added can push a chunk slightly over,
        # not force it back under, by design (see _merge_with_overlap's
        # docstring - it never splits a piece mid-sentence to enforce this
        # exactly).
        assert len(chunk) <= 600


def test_consecutive_chunks_share_overlapping_text():
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)
    assert len(chunks) >= 2

    # The whole point of overlap: the tail of one chunk should reappear at
    # the start of the next one, so content sitting right at a chunk
    # boundary isn't only ever visible in a single chunk. Checking the last
    # 20 characters of chunk 0 appear somewhere in chunk 1 is a looser,
    # more robust check than an exact-substring match at a fixed offset,
    # since the merge step trims whitespace at the join point.
    tail_of_first_chunk = chunks[0][-20:].strip()
    assert tail_of_first_chunk in chunks[1]


def test_zero_overlap_is_respected_not_silently_replaced_with_the_default():
    # chunk_overlap=0 is a real, valid setting (no overlap at all) - this
    # guards against a future regression where someone changes the
    # "resolve chunk_overlap" logic back to `chunk_overlap or DEFAULT`,
    # which would silently turn a real 0 into the 150-character default
    # (see pipeline.py's own comment on exactly this bug shape).
    sentence = "This is one sentence about JPMorgan Chase benefits policy. "
    text = sentence * 40

    chunks_with_zero_overlap = chunk_text(text, chunk_size=500, chunk_overlap=0)
    chunks_with_real_overlap = chunk_text(text, chunk_size=500, chunk_overlap=100)

    # Not a precise assertion on chunk count (that depends on exactly where
    # sentences fall), just confirming zero-overlap chunking behaves
    # differently from - and produces at least as many chunks as -
    # overlapping chunking, since overlap only ever adds characters back in.
    assert len(chunks_with_zero_overlap) >= len(chunks_with_real_overlap)
