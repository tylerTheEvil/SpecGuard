"""Smoke tests for the unified ``specguard`` CLI (specguard.cli).

These exercise the deterministic, no-database, no-LLM paths by invoking
``main(argv)`` directly and asserting on exit codes + captured stdout. The
Neo4j-backed paths (import --to-neo4j, comply --neo4j, graph --cypher,
review merge-to-neo4j) are covered by tests/test_neo4j_io.py behind the
``neo4j`` marker.
"""

from __future__ import annotations

import json

import pytest

from specguard.cli import main


@pytest.fixture
def mixed_file(tmp_path):
    """A small file with one PASS, one WARN, one FAIL requirement."""
    p = tmp_path / "reqs.txt"
    p.write_text(
        "P1: The CVA6 processor shall execute the RV64I base instruction set.\n"
        "W1: The system should be reasonably fast.\n"
        "F1: The store path timing budget is TBD.\n"
    )
    return p


@pytest.fixture
def all_pass_file(tmp_path):
    p = tmp_path / "pass.txt"
    p.write_text("P1: The CVA6 processor shall execute the RV64I base instruction set.\n")
    return p


@pytest.fixture
def warn_only_file(tmp_path):
    p = tmp_path / "warn.txt"
    p.write_text("W1: The system should be reasonably fast.\n")
    return p


# ---------------------------------------------------------------------------
# assess — exit codes
# ---------------------------------------------------------------------------


def test_assess_exit_0_all_pass(all_pass_file, capsys):
    assert main(["assess", str(all_pass_file)]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out


def test_assess_exit_1_warn(warn_only_file):
    assert main(["assess", str(warn_only_file)]) == 1


def test_assess_exit_2_fail(mixed_file):
    # FAIL present -> worst gate -> exit 2.
    assert main(["assess", str(mixed_file)]) == 2


def test_assess_human_table(mixed_file, capsys):
    main(["assess", str(mixed_file)])
    out = capsys.readouterr().out
    assert "GATE" in out and "TOP TRIGGERS" in out
    assert "P1" in out and "W1" in out and "F1" in out
    assert "3 requirements" in out


def test_assess_json_shape(mixed_file, capsys):
    main(["assess", str(mixed_file), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"results", "aggregate"}
    assert len(payload["results"]) == 3
    first = payload["results"][0]
    assert {"id", "gate", "overall", "smell_count", "smells"} <= set(first)
    assert payload["aggregate"]["total_requirements"] == 3


def test_assess_stdin(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("P1: The unit shall reset.\n"))
    assert main(["assess", "-"]) == 0


def test_assess_parse_error_exit_3(tmp_path):
    p = tmp_path / "bad.txt"
    p.write_text("no id prefix here at all")
    assert main(["assess", str(p)]) == 3


# ---------------------------------------------------------------------------
# import (dry run — no DB)
# ---------------------------------------------------------------------------


def test_import_dry_run(mixed_file, capsys):
    assert main(["import", str(mixed_file), "--dataset-tag", "demo"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "Nodes:" in out


def test_import_json(mixed_file, capsys):
    assert main(["import", str(mixed_file), "--dataset-tag", "demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_tag"] == "demo"
    assert payload["to_neo4j"] is False
    assert payload["stats"]["total_nodes"] > 0


def test_import_rejects_whitespace_tag(mixed_file):
    assert main(["import", str(mixed_file), "--dataset-tag", "   "]) == 3


# ---------------------------------------------------------------------------
# comply --memory (no DB)
# ---------------------------------------------------------------------------


def test_comply_memory(capsys):
    assert main(["comply", "--memory"]) == 0
    out = capsys.readouterr().out
    assert "memory backend" in out
    assert "Objectives checked: 15" in out


def test_comply_memory_json(capsys):
    assert main(["comply", "--memory", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "memory"
    assert payload["total_objectives"] == 15
    assert payload["passing"] == 9  # documented CVA6 result


# ---------------------------------------------------------------------------
# graph (named, in-memory NetworkX)
# ---------------------------------------------------------------------------


def test_graph_named_q6(capsys):
    assert main(["graph", "q6"]) == 0
    out = capsys.readouterr().out
    assert "q6" in out


def test_graph_named_q14_json(capsys):
    assert main(["graph", "q14", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "q14"
    assert isinstance(payload["rows"], list)


def test_graph_unknown_named_exit_3(capsys):
    assert main(["graph", "q99"]) == 3


def test_graph_no_arg_exit_3():
    assert main(["graph"]) == 3
