"""Tests for the stdlib requirement parsers (specguard.io.parsers).

Covers all three formats, auto-detection (by extension and by content sniff),
plain-text continuation lines, and explicit error cases. No database, no LLM,
no optional extras required.
"""

from __future__ import annotations

import pytest

from specguard.data.cva6_requirements import Requirement
from specguard.io.parsers import ParseError, parse_requirements

# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def test_plaintext_basic():
    text = "R1: The system shall reset.\nR2: The system shall log events."
    reqs = parse_requirements(text, fmt="text")
    assert [r.req_id for r in reqs] == ["R1", "R2"]
    assert reqs[0].text == "The system shall reset."
    assert all(isinstance(r, Requirement) for r in reqs)


def test_plaintext_ignores_blanks_and_comments():
    text = "# a comment\n\nR1: First.\n# another\n\nR2: Second.\n"
    reqs = parse_requirements(text, fmt="text")
    assert [r.req_id for r in reqs] == ["R1", "R2"]


def test_plaintext_continuation_lines():
    text = "R1: The MMU shall translate addresses\nusing Sv39 paging\nraising a fault.\nR2: Done."
    reqs = parse_requirements(text, fmt="text")
    assert len(reqs) == 2
    assert reqs[0].text == "The MMU shall translate addresses using Sv39 paging raising a fault."
    assert reqs[1].text == "Done."


def test_plaintext_prose_colon_is_continuation_not_new_id():
    # "Note:" should not be parsed as a new ID (lower-case word that is prose).
    text = "R1: The unit shall start.\nNote that this is informative."
    reqs = parse_requirements(text, fmt="text")
    assert len(reqs) == 1
    assert "Note that this is informative." in reqs[0].text


def test_plaintext_first_line_without_id_errors():
    with pytest.raises(ParseError):
        parse_requirements("just some prose with no id prefix", fmt="text")


# ---------------------------------------------------------------------------
# Markdown table
# ---------------------------------------------------------------------------


def test_markdown_table():
    text = (
        "| ID | Text |\n"
        "|----|------|\n"
        "| M1 | The processor shall reset cleanly. |\n"
        "| M2 | It should be fast. |\n"
    )
    reqs = parse_requirements(text, fmt="md")
    assert [r.req_id for r in reqs] == ["M1", "M2"]
    assert reqs[0].text == "The processor shall reset cleanly."


def test_markdown_flexible_headers_and_extra_column():
    text = (
        "| Req_ID | Category | Requirement |\n"
        "|--------|----------|-------------|\n"
        "| M1 | Safety | The watchdog shall trip within 10 ms. |\n"
    )
    reqs = parse_requirements(text, fmt="md")
    assert reqs[0].req_id == "M1"
    assert reqs[0].category == "Safety"
    assert "watchdog" in reqs[0].text


def test_markdown_missing_text_column_errors():
    text = "| ID | Note |\n|----|------|\n| M1 | x |\n"
    with pytest.raises(ParseError):
        parse_requirements(text, fmt="md")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_basic():
    text = 'id,text\nC1,"The unit shall, on reset, clear state."\nC2,Second requirement.\n'
    reqs = parse_requirements(text, fmt="csv")
    assert [r.req_id for r in reqs] == ["C1", "C2"]
    # Embedded comma survived stdlib csv quoting.
    assert reqs[0].text == "The unit shall, on reset, clear state."


def test_csv_missing_id_column_errors():
    text = "name,text\nfoo,bar\n"
    with pytest.raises(ParseError):
        parse_requirements(text, fmt="csv")


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def test_auto_detect_by_extension(tmp_path):
    p = tmp_path / "reqs.csv"
    p.write_text("id,text\nC1,A requirement.\n")
    reqs = parse_requirements(p)
    assert reqs[0].req_id == "C1"


def test_auto_detect_markdown_by_content():
    text = "| ID | Text |\n|----|------|\n| M1 | A requirement. |\n"
    reqs = parse_requirements(text)  # fmt='auto', no extension
    assert reqs[0].req_id == "M1"


def test_auto_detect_csv_by_content():
    text = "id,text\nC1,A requirement.\n"
    reqs = parse_requirements(text)
    assert reqs[0].req_id == "C1"


def test_auto_detect_plaintext_by_content():
    text = "R1: A requirement.\nR2: Another."
    reqs = parse_requirements(text)
    assert [r.req_id for r in reqs] == ["R1", "R2"]


def test_path_object_accepted(tmp_path):
    p = tmp_path / "reqs.txt"
    p.write_text("R1: A requirement.\n")
    reqs = parse_requirements(p)
    assert reqs[0].req_id == "R1"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_empty_input_errors():
    with pytest.raises(ParseError):
        parse_requirements("   \n  \n", fmt="text")


def test_unknown_format_errors():
    with pytest.raises(ParseError):
        parse_requirements("R1: x", fmt="xml")


def test_sample_examples_file_parses():
    # The shipped walkthrough sample must parse cleanly.
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "examples" / "sample_requirements.txt"
    reqs = parse_requirements(sample)
    assert len(reqs) == 6
    assert reqs[0].req_id == "REQ-01"
