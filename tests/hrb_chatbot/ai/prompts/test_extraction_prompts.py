"""Tests for Phase 63's entity-extraction prompt template - a pure string-building
function, no LLM call needed."""

import pytest

from src.hrb_chatbot.ai.prompts.extraction_prompts import build_entity_extraction_prompt


def test_document_text_is_included_in_the_prompt():
    prompt = build_entity_extraction_prompt("Employee John Smith enrolled in the health plan.")
    assert "Employee John Smith enrolled in the health plan." in prompt


def test_prompt_instructs_never_to_output_a_full_ssn_or_account_number():
    prompt = build_entity_extraction_prompt("Some document text.")
    assert "do NOT output the SSN itself" in prompt
    assert "never" in prompt.lower()


def test_empty_text_raises_instead_of_building_an_empty_prompt():
    with pytest.raises(ValueError):
        build_entity_extraction_prompt("")


def test_whitespace_only_text_raises():
    with pytest.raises(ValueError):
        build_entity_extraction_prompt("   \n  ")
