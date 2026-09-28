"""End-to-end: install the extension into a real Spec Kit project.

Needs the Spec Kit CLI. Resolution: ``SPECKIT_SOURCE`` (path to a spec-kit
checkout, run through ``uv tool run --from``) or ``specify`` on PATH;
otherwise the module is skipped. Verified against spec-kit c00dc05
(v1.0.13.dev0).

What is proven here, and what is not:
- proven: the manifest installs; both commands are registered for the agent;
  ``{SCRIPT}`` renders to a runnable interpreter + installed script path; the
  hooks land in ``.specify/extensions.yml`` with the intended optional flags;
  the rendered command actually runs on a spec inside the project;
  dev-only files are excluded by ``.extensionignore``.
- not proven: that an agent obeys the prompt-level "stop on blocking verdict"
  instruction — Spec Kit has no machine-enforced hook halt (see README).
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

EXT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def _specify_cmd() -> list[str] | None:
    source = os.environ.get("SPECKIT_SOURCE")
    if source and shutil.which("uv"):
        return ["uv", "tool", "run", "--from", source, "specify"]
    if shutil.which("specify"):
        return ["specify"]
    return None


SPECIFY = _specify_cmd()
if SPECIFY is None:
    pytest.skip("Spec Kit CLI unavailable (set SPECKIT_SOURCE or install specify)",
                allow_module_level=True)


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "NO_COLOR": "1"}
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=600)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("speckit-e2e")
    run([*SPECIFY, "init", "proj", "--integration", "claude", "--script", "py",
         "--ignore-agent-tools", "--non-interactive"], cwd=base)
    proj = base / "proj"
    run([*SPECIFY, "extension", "add", "--dev", str(EXT_ROOT)], cwd=proj)
    return proj


def _registered_command(project: Path, name: str) -> Path:
    """Claude integration registers commands as skills or command files."""
    candidates = [
        project / ".claude" / "commands" / f"{name}.md",
        project / ".claude" / "skills" / name.replace(".", "-") / "SKILL.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    found = sorted(str(p.relative_to(project)) for p in (project / ".claude").rglob("*specguard*"))
    raise AssertionError(f"{name} not registered; specguard files under .claude: {found}")


def test_installed_copy_excludes_dev_files(project):
    installed = project / ".specify" / "extensions" / "specguard"
    assert (installed / "extension.yml").is_file()
    assert (installed / "scripts" / "python" / "run_specguard.py").is_file()
    assert (installed / "scripts" / "python" / "specguard_speckit" / "_vendor" /
            "specguard_core" / "VENDOR.json").is_file()
    for dev_only in ("tests", "experiments", "tools", "docs/implementation_plan.md",
                     "pyproject.toml"):
        assert not (installed / dev_only).exists(), dev_only
    assert (installed / "docs" / "checks.md").is_file()  # reports link to it


def test_hooks_registered_with_intended_flags(project):
    text = (project / ".specify" / "extensions.yml").read_text(encoding="utf-8")
    for event in ("after_specify", "after_clarify", "before_plan", "after_tasks"):
        assert event in text, event
    before_plan = text[text.index("before_plan"):]
    block = before_plan.split("\n  after_", 1)[0].split("\n  before_", 1)[0]
    assert "speckit.specguard.gate" in block
    assert re.search(r"optional:\s*false", block), block


@pytest.mark.parametrize("name", ["speckit.specguard.gate", "speckit.specguard.trace"])
def test_command_registered_and_script_rendered(project, name):
    body = _registered_command(project, name).read_text(encoding="utf-8")
    assert "{SCRIPT}" not in body
    assert ".specify/extensions/specguard/scripts/python/run_specguard.py" in body
    assert "__SPECKIT_COMMAND_" not in body  # agent-neutral tokens resolved


def _rendered_invocation(project: Path) -> list[str]:
    body = _registered_command(project, "speckit.specguard.gate").read_text(encoding="utf-8")
    m = re.search(r"no path given: `([^`]+)`", body)
    assert m, "rendered invocation not found in command body"
    return shlex.split(m.group(1))


def test_rendered_invocation_runs_in_project(project):
    feature = project / "specs" / "001-demo"
    feature.mkdir(parents=True)
    shutil.copy(FIXTURES / "spec_open_marker.md", feature / "spec.md")
    cmd = _rendered_invocation(project)
    if cmd[0] in ("python3", "python"):
        cmd[0] = sys.executable  # the interpreter Spec Kit would resolve on this host
    proc = run([*cmd, "specs/001-demo"], cwd=project, check=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "## SpecGuard gate: FAIL" in proc.stdout
    assert "SK-001" in proc.stdout
    json_proc = run([*cmd, "specs/001-demo", "--format", "json"], cwd=project, check=False)
    assert '"checks_doc": ".specify/extensions/specguard/docs/checks.md"' in json_proc.stdout


def test_feature_json_resolution_in_project(project):
    feature = project / "specs" / "002-clean"
    feature.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "spec_clean.md", feature / "spec.md")
    (project / ".specify" / "feature.json").write_text(
        '{"feature_directory": "specs/002-clean"}', encoding="utf-8")
    cmd = _rendered_invocation(project)
    if cmd[0] in ("python3", "python"):
        cmd[0] = sys.executable
    proc = run(cmd, cwd=project, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "`specs/002-clean/spec.md`" in proc.stdout
