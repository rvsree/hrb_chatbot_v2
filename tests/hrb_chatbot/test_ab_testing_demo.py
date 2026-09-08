"""A simulated A/B test - a REFERENCE PATTERN, not real evaluation infrastructure.

What this is, and what it isn't
-----------------------------------
Real A/B testing for a RAG pipeline (comparing chunk_size, embedding
models, or prompts against real retrieval-quality and answer-quality
metrics) is Phase 8 in docs/RAG-ROADMAP.md - hand-written, not built yet,
and it needs Phase 6 (real retrieval + generation) to exist first before
there's anything real to measure. This file is deliberately smaller than
that: it demonstrates the *shape* of an A/B comparison test - run
configuration A, run configuration B, compare a concrete metric between
them - using only the chunking step, which already exists and needs no
network call. Copy this file's structure once Phase 6 lands and there's
a real answer-quality metric to compare, rather than treating this file
itself as that evaluation.

See docs/TESTING-GUIDE.md for the full walkthrough this pattern is
explained in.
"""

from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import chunk_text

# A representative paragraph, long enough that chunk_size actually changes
# how many pieces it's split into - short test strings don't exercise the
# comparison meaningfully.
SAMPLE_POLICY_TEXT = (
    "JPMorgan Chase provides 16 weeks of fully paid parental leave to all "
    "eligible employees for the birth or placement of a child for adoption. "
    "This gender-neutral policy applies equally to all parents regardless "
    "of gender, marital status, or caregiver role. Employees must be "
    "actively employed on a U.S. payroll and regularly scheduled to work "
    "20 or more hours per week to qualify. New hires are eligible "
    "immediately upon meeting benefits eligibility requirements. "
) * 5


def test_ab_comparison_smaller_chunk_size_produces_more_chunks():
    """The comparison itself: configuration A (chunk_size=300) vs.
    configuration B (chunk_size=1000), same input, one concrete metric
    (chunk count) compared between them. This is the pattern to repeat for
    a real metric later - retrieval precision@k, answer groundedness score,
    whatever Phase 8 ends up measuring - swap out chunk_text() for the real
    pipeline call and swap out "chunk count" for the real metric; the
    "run A, run B, assert a specific relationship between the two results"
    shape stays the same.
    """
    configuration_a_chunk_size = 300
    configuration_b_chunk_size = 1000

    chunks_a = chunk_text(SAMPLE_POLICY_TEXT, chunk_size=configuration_a_chunk_size, chunk_overlap=30)
    chunks_b = chunk_text(SAMPLE_POLICY_TEXT, chunk_size=configuration_b_chunk_size, chunk_overlap=100)

    # The concrete, checkable claim this "experiment" makes: a smaller
    # chunk_size on the same text produces at least as many chunks as a
    # larger one - not a vague "chunking works" assertion.
    assert len(chunks_a) >= len(chunks_b)


def test_ab_comparison_report_shape():
    """Demonstrates building a small comparison report dict - the shape a
    real A/B test result should take so it's easy to log, store, or diff
    against a previous run, not just an assertion with no record of what
    was actually compared."""
    configurations = {
        "small_chunks": {"chunk_size": 300, "chunk_overlap": 30},
        "large_chunks": {"chunk_size": 1000, "chunk_overlap": 100},
    }

    report = {}
    for name, config in configurations.items():
        chunks = chunk_text(SAMPLE_POLICY_TEXT, **config)

        total_length = 0
        for chunk in chunks:
            total_length += len(chunk)

        report[name] = {
            "chunk_count": len(chunks),
            "average_chunk_length": total_length / len(chunks),
        }

    assert report["small_chunks"]["chunk_count"] > report["large_chunks"]["chunk_count"]
    assert report["small_chunks"]["average_chunk_length"] < report["large_chunks"]["average_chunk_length"]
