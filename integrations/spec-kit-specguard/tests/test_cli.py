"""CLI contract: exit codes, output formats, determinism, feature resolution."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from conftest import SCRIPTS
from specguard_speckit.cli import exit_code, main

ENTRY = SCRIPTS / "run_specguard.py"


def gate(capsys, *args) -> tuple[int, str, str]:
    code = main(["gate", *map(str, args)])
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    for var in ("SPECIFY_FEATURE_DIRECTORY", "SPECIFY_INIT_DIR", "SPECKIT_SPECGUARD_PROFILE",
                "SPECKIT_SPECGUARD_FAIL_ON", "SPECKIT_SPECGUARD_KINDS",
                "SPECKIT_SPECGUARD_WRITE_REPORT", "SPECKIT_SPECGUARD_DISABLED_CHECKS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)


class TestExitCodes:
    @pytest.mark.parametrize("verdict,fail_on,expected", [
        ("PASS", "fail", 0), ("WARN", "fail", 0), ("FAIL", "fail", 2),
        ("PASS", "warn", 0), ("WARN", "warn", 1), ("FAIL", "warn", 2),
        ("FAIL", "never", 0),
    ])
    def test_matrix(self, verdict, fail_on, expected):
        assert exit_code(verdict, fail_on) == expected

    def test_clean_spec_exit_0(self, capsys, feature_dir):
        code, out, _ = gate(capsys, feature_dir(spec="spec_clean.md"))
        assert code == 0 and "## SpecGuard gate: PASS" in out

    def test_fail_exit_2(self, capsys, feature_dir):
        code, out, _ = gate(capsys, feature_dir(spec="spec_open_marker.md"))
        assert code == 2 and "**Blocking: yes**" in out

    def test_warn_blocks_only_with_fail_on_warn(self, capsys, feature_dir):
        d = feature_dir(spec="spec_clean.md")
        (d / "spec.md").write_text((d / "spec.md").read_text().replace(
            "90% of readers bookmark a recipe in under 5 seconds from opening the recipe page",
            "Readers enjoy bookmarking recipes"))
        code, out, _ = gate(capsys, d)
        assert code == 0 and "## SpecGuard gate: WARN" in out
        assert gate(capsys, d, "--fail-on", "warn")[0] == 1

    def test_usage_error_is_3_not_a_verdict(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["gate", "--format", "xml"])
        assert exc.value.code == 3

    def test_missing_spec_is_3(self, capsys, tmp_path):
        (tmp_path / "empty").mkdir()
        code, _, err = gate(capsys, tmp_path / "empty")
        assert code == 3 and "spec not found" in err

    def test_unresolvable_feature_is_3(self, capsys):
        code, _, err = gate(capsys)
        assert code == 3 and "Could not determine the feature directory" in err


class TestOutput:
    def test_json_payload(self, capsys, feature_dir):
        code, out, _ = gate(capsys, feature_dir(spec="spec_structural.md"), "--format", "json")
        data = json.loads(out)
        assert data["verdict"] == "FAIL" and data["blocking"] is True and code == 2
        assert data["counts"]["requirements"] == {"FR": 4, "SC": 2}
        assert {f["check"] for f in data["findings"]} >= {"SK-004", "SK-009"}
        assert data["core"]["files"].keys() == {"smell_detector.py", "quality_scorer.py"}
        sc1 = next(r for r in data["requirements"] if r["id"] == "SC-001")
        assert sc1["sc_class"] == "UNMEASURED" and sc1["gate"] == "WARN"

    def test_markdown_is_deterministic(self, capsys, feature_dir):
        d = feature_dir(spec="spec_structural.md")
        first = gate(capsys, d)[1]
        second = gate(capsys, d)[1]
        assert first == second
        assert "### Not checked deterministically" in first
        assert "not proofs" in first

    def test_default_profile_via_flag(self, capsys, feature_dir):
        d = feature_dir(spec="spec_clean.md")
        out = json.loads(gate(capsys, d, "--profile", "default", "--format", "json")[1])
        assert out["profile"] == "default"
        assert all(r["sc_class"] is None for r in out["requirements"])

    def test_write_report(self, capsys, feature_dir):
        d = feature_dir(spec="spec_clean.md")
        code, out, _ = gate(capsys, d, "--write-report")
        assert (d / "specguard-report.md").read_text() == out
        assert json.loads((d / "specguard-report.json").read_text())["verdict"] == "PASS"

    def test_disabled_checks_from_env(self, capsys, feature_dir, monkeypatch):
        monkeypatch.setenv("SPECKIT_SPECGUARD_DISABLED_CHECKS", "SK-011,SK-012")
        out = json.loads(gate(capsys, feature_dir(spec="spec_structural.md"),
                              "--format", "json")[1])
        assert not {f["check"] for f in out["findings"]} & {"SK-011", "SK-012"}


class TestFeatureResolution:
    def _project(self, tmp_path, feature_dir):
        d = feature_dir(spec="spec_clean.md", name="007-bookmarks")
        (tmp_path / ".specify").mkdir()
        return d

    def test_feature_json(self, capsys, tmp_path, feature_dir):
        self._project(tmp_path, feature_dir)
        (tmp_path / ".specify" / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/007-bookmarks"}))
        code, out, _ = gate(capsys)
        assert code == 0 and "`specs/007-bookmarks/spec.md`" in out

    def test_env_overrides_feature_json(self, capsys, tmp_path, feature_dir, monkeypatch):
        self._project(tmp_path, feature_dir)
        other = feature_dir(spec="spec_open_marker.md", name="008-export")
        (tmp_path / ".specify" / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/007-bookmarks"}))
        monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", str(other))
        code, out, _ = gate(capsys)
        assert code == 2 and "008-export" in out

    def test_never_writes_feature_json(self, capsys, tmp_path, feature_dir):
        d = self._project(tmp_path, feature_dir)
        gate(capsys, d)
        assert not (tmp_path / ".specify" / "feature.json").exists()

    def test_spec_file_argument(self, capsys, tmp_path, feature_dir):
        d = self._project(tmp_path, feature_dir)
        code, out, _ = gate(capsys, d / "spec.md")
        assert code == 0 and "`specs/007-bookmarks/spec.md`" in out

    def test_project_config_applies(self, capsys, tmp_path, feature_dir):
        d = self._project(tmp_path, feature_dir)
        cfg = tmp_path / ".specify" / "extensions" / "specguard"
        cfg.mkdir(parents=True)
        (cfg / "specguard-config.yml").write_text("profile: default\n")
        out = json.loads(gate(capsys, d, "--format", "json")[1])
        assert out["profile"] == "default"


class TestTraceCommand:
    def test_trace_ok(self, capsys, feature_dir):
        code = main(["trace", str(feature_dir(spec="spec_clean.md", tasks="tasks_ok.md"))])
        out = capsys.readouterr().out
        assert code == 0 and "## SpecGuard trace: PASS" in out
        assert "FRs referenced by tasks: 6/6" in out

    def test_trace_dangling_reference_fails(self, capsys, feature_dir):
        d = feature_dir(spec="spec_clean.md", tasks="tasks_gaps.md")
        code = main(["trace", str(d), "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        assert code == 2 and data["verdict"] == "FAIL"

    def test_trace_accepts_tasks_file_path(self, capsys, feature_dir):
        d = feature_dir(spec="spec_clean.md", tasks="tasks_ok.md")
        assert main(["trace", str(d / "tasks.md")]) == 0
        assert "## SpecGuard trace: PASS" in capsys.readouterr().out

    def test_trace_without_tasks_is_3(self, capsys, feature_dir):
        code = main(["trace", str(feature_dir(spec="spec_clean.md"))])
        assert code == 3 and "tasks.md not found" in capsys.readouterr().err


def test_entry_script_subprocess(feature_dir):
    """The real entry point, as Spec Kit renders it, in a fresh interpreter."""
    d = feature_dir(spec="spec_open_marker.md")
    proc = subprocess.run([sys.executable, str(ENTRY), "gate", str(d)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert proc.stdout.startswith("## SpecGuard gate: FAIL")


def test_version_command(capsys):
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("spec-kit-specguard ") and "smell_detector.py sha256=" in out
