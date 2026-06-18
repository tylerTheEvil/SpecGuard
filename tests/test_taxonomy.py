"""Tests for the checkability taxonomy subsystem (Contribution #2).

The core taxonomy (loader / validator / stats) is stdlib-only and must pass with
no extras; the coverage-map test is guarded with ``importorskip("matplotlib")``.
"""

from __future__ import annotations

import dataclasses

import pytest

from specguard.taxonomy import (
    TaxonomyRow,
    compute_stats,
    load_taxonomy,
    validate,
    zone_for_class,
)

SEED_ROW_COUNT = 15


@pytest.fixture(scope="module")
def seed_rows() -> list[TaxonomyRow]:
    return load_taxonomy()  # default path = taxonomy/checkability_taxonomy.csv


def _a_valid_machine_row() -> TaxonomyRow:
    """A self-consistent, codified row to mutate in the negative tests."""
    return TaxonomyRow(
        objective_id="DO-178C-A4-1",
        standard="DO-178C",
        table_section="A-4",
        title="LLR comply with HLR",
        formulation_paraphrase="Every LLR traces to a parent HLR",
        dal_applicability="A;B;C",
        semantic_class="traceability",
        checkability_zone="machine",
        topological_template="T1-mandatory-edge",
        template_params="node=LLR; require DERIVES_FROM -> HLR",
        decision_rule="DR1",
        prototype_instance="compliance/do178c.py::DO_178C_A4_1",
        notes_disputed="",
    )


# --------------------------------------------------------------------------
# Loader + happy-path validation
# --------------------------------------------------------------------------


def test_loader_parses_seed(seed_rows: list[TaxonomyRow]) -> None:
    assert len(seed_rows) == SEED_ROW_COUNT
    assert all(isinstance(r, TaxonomyRow) for r in seed_rows)
    assert seed_rows[0].objective_id == "DO-178C-A3-1"


def test_seed_validates_clean(seed_rows: list[TaxonomyRow]) -> None:
    assert validate(seed_rows) == []


def test_zone_rule_pure_function() -> None:
    assert zone_for_class("traceability") == "machine"
    assert zone_for_class("hybrid") == "screened"
    assert zone_for_class("not-machine-checkable") == "human"
    assert zone_for_class("bogus") is None


# --------------------------------------------------------------------------
# FK integrity: every seed prototype_instance resolves and ids match
# --------------------------------------------------------------------------


def test_fk_integrity_all_seed_prototypes_resolve(seed_rows: list[TaxonomyRow]) -> None:
    codified = [r for r in seed_rows if r.is_codified]
    assert len(codified) == SEED_ROW_COUNT  # every seed row is codified
    fk_errors = [e for e in validate(seed_rows) if e.field == "prototype_instance"]
    assert fk_errors == []


def test_fk_dangling_prototype_is_caught() -> None:
    bad = dataclasses.replace(
        _a_valid_machine_row(), prototype_instance="compliance/do178c.py::NOPE_NOT_A_SYMBOL"
    )
    errors = validate([bad])
    assert any(e.field == "prototype_instance" for e in errors)


def test_fk_mismatched_objective_id_is_caught() -> None:
    # Symbol resolves, but its .objective_id != the row's id.
    bad = dataclasses.replace(
        _a_valid_machine_row(),
        objective_id="DO-178C-A4-1-WRONG",
        prototype_instance="compliance/do178c.py::DO_178C_A4_1",
    )
    errors = validate([bad])
    assert any(
        e.field == "prototype_instance" and "objective_id" in e.message for e in errors
    )


# --------------------------------------------------------------------------
# Each injected schema defect is caught
# --------------------------------------------------------------------------


def test_bad_enum_caught() -> None:
    bad = dataclasses.replace(_a_valid_machine_row(), semantic_class="made-up-class")
    assert any(e.field == "semantic_class" for e in validate([bad]))


def test_zone_class_mismatch_caught() -> None:
    # traceability implies 'machine', not 'human'
    bad = dataclasses.replace(_a_valid_machine_row(), checkability_zone="human")
    errors = validate([bad])
    assert any(e.field == "checkability_zone" and "implies" in e.message for e in errors)


def test_human_row_with_template_caught() -> None:
    human = TaxonomyRow(
        objective_id="HUMAN-1",
        standard="DO-178C",
        table_section="A-3",
        title="accurate",
        formulation_paraphrase="requirements are accurate",
        dal_applicability="A;B",
        semantic_class="not-machine-checkable",
        checkability_zone="human",
        topological_template="T1-mandatory-edge",  # illegal for a human row
        template_params="",
        decision_rule="DR5",  # also illegal for a human row
        prototype_instance="",
        notes_disputed="",
    )
    errors = validate([human])
    assert any(e.field == "topological_template" for e in errors)
    assert any(e.field == "decision_rule" for e in errors)


def test_duplicate_id_caught() -> None:
    row = _a_valid_machine_row()
    errors = validate([row, row])
    assert any(e.field == "objective_id" and "duplicate" in e.message for e in errors)


def test_bad_dal_token_caught() -> None:
    bad = dataclasses.replace(_a_valid_machine_row(), dal_applicability="A;E;Z")
    errors = validate([bad])
    assert any(e.field == "dal_applicability" for e in errors)


# --------------------------------------------------------------------------
# Stats backbone
# --------------------------------------------------------------------------


def test_stats_template_count_and_zone_split(seed_rows: list[TaxonomyRow]) -> None:
    stats = compute_stats(seed_rows)
    assert stats["distinct_templates"] == 6
    assert stats["by_zone"] == {"machine": 14, "screened": 1}
    assert stats["total"] == SEED_ROW_COUNT
    assert stats["codified"] == SEED_ROW_COUNT
    assert stats["by_standard"] == {"DO-178C": 7, "DO-254": 5, "cross-domain": 3}


# --------------------------------------------------------------------------
# Coverage-map script (needs matplotlib [viz] extra)
# --------------------------------------------------------------------------


def test_coverage_map_writes_outputs(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    import sys

    sys.path.insert(0, "scripts")
    try:
        import coverage_map
    finally:
        sys.path.pop(0)

    rc = coverage_map.main(["--out-dir", str(tmp_path), "--calibration"])
    assert rc == 0
    assert (tmp_path / "coverage_map.png").is_file()
    assert (tmp_path / "coverage_map.csv").is_file()
