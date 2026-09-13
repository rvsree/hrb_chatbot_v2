"""Tests for _format_table_as_markdown() (ai/doc_processing/tables/table_extractor.py) -
the pure formatting logic, tested directly against synthetic row data rather
than a real PDF fixture (extract_tables_from_pdf() itself is exercised live
against a real PDF, not in the automated suite - see docs/RAG-ROADMAP.md)."""

from src.hrb_chatbot.ai.doc_processing.tables.table_extractor import _format_table_as_markdown


def test_a_simple_table_becomes_a_markdown_table():
    table = [["Name", "Days"], ["Sick", "10"], ["Vacation", "15"]]

    result = _format_table_as_markdown(table)

    assert result == "| Name | Days |\n| --- | --- |\n| Sick | 10 |\n| Vacation | 15 |"


def test_none_cells_become_empty_strings_not_the_literal_word_none():
    table = [["Name", "Days"], ["Sick", None]]

    result = _format_table_as_markdown(table)

    assert "None" not in result
    assert "| Sick |  |" in result


def test_newlines_within_a_cell_are_flattened_to_spaces():
    table = [["Name", "Notes"], ["Sick", "Line one\nLine two"]]

    result = _format_table_as_markdown(table)

    assert "Line one Line two" in result
    assert "\n" not in result.split("\n", 2)[2]  # the data row itself has no embedded newline


def test_a_table_of_entirely_empty_rows_returns_none():
    table = [[None, None], ["", ""]]

    result = _format_table_as_markdown(table)

    assert result is None
