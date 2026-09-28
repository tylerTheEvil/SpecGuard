"""Manifest and command-file rules from the Spec Kit extension API (schema 1.0).

Stdlib-only (no PyYAML): the manifest is read with targeted patterns. Full
validation by Spec Kit's own ExtensionManifest happens in test_e2e_speckit.py
(installation fails on an invalid manifest).
"""

from __future__ import annotations

import re
import textwrap

from conftest import EXT_ROOT
from specguard_speckit import __version__
from specguard_speckit.config import DEFAULTS, parse_flat_yaml

MANIFEST = (EXT_ROOT / "extension.yml").read_text(encoding="utf-8")
COMMAND_NAME = re.compile(r"^speckit\.[a-z0-9-]+\.[a-z0-9-]+$")
HOOK_EVENTS = {
    f"{when}_{what}"
    for when in ("before", "after")
    for what in ("specify", "plan", "tasks", "implement", "analyze", "checklist", "clarify",
                 "constitution", "taskstoissues")
}


def field(name: str) -> str:
    m = re.search(rf'^\s*{name}:\s*"?([^"\n]+)"?\s*$', MANIFEST, re.M)
    assert m, name
    return m.group(1)


def commands() -> list[tuple[str, str]]:
    return re.findall(r'-\s+name:\s*"(speckit\.[^"]+)"\s*\n\s*file:\s*"([^"]+)"', MANIFEST)


def test_identity():
    assert field("schema_version") == "1.0"
    assert re.fullmatch(r"[a-z0-9-]+", field("id")) and field("id") == "specguard"
    assert re.fullmatch(r"\d+\.\d+\.\d+", field("version"))
    assert field("version") == __version__
    assert len(field("description")) < 200
    assert re.fullmatch(r">=\d+\.\d+\.\d+", field("speckit_version"))


def test_commands_namespaced_and_files_exist():
    cmds = commands()
    assert [c for c, _ in cmds] == ["speckit.specguard.gate", "speckit.specguard.trace"]
    for name, rel in cmds:
        assert COMMAND_NAME.match(name) and name.split(".")[1] == "specguard"
        assert not rel.startswith(("/", "..")) and (EXT_ROOT / rel).is_file()


def test_command_frontmatter_and_script():
    for _, rel in commands():
        text = (EXT_ROOT / rel).read_text(encoding="utf-8")
        fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        assert fm, rel
        assert re.search(r"^description:\s*\S", fm.group(1), re.M)
        script = re.search(r"^\s+py:\s*(\S+)", fm.group(1), re.M)
        assert script and (EXT_ROOT / script.group(1)).is_file()
        body = text[fm.end():]
        assert "{SCRIPT}" in body and "$ARGUMENTS" in body
        assert "/speckit." not in body, "hard-coded invocation; use __SPECKIT_COMMAND_*__"
        assert "not part of the verdict" in body  # Layer-2 separation instruction


def test_hooks_reference_provided_commands_and_valid_events():
    provided = {c for c, _ in commands()}
    hooks = MANIFEST.split("\nhooks:\n", 1)[1].split("\ntags:", 1)[0]
    events = re.findall(r"^  ([a-z_]+):\s*$", hooks, re.M)
    assert events and set(events) <= HOOK_EVENTS
    for cmd in re.findall(r'command:\s*"([^"]+)"', hooks):
        assert cmd in provided
    before_plan = hooks.split("before_plan:", 1)[1].split("\n  after_", 1)[0]
    assert "optional: false" in before_plan  # the gate is mandatory before planning


def test_manifest_defaults_match_code_and_template():
    block = MANIFEST.split("\ndefaults:\n", 1)[1]
    assert parse_flat_yaml(textwrap.dedent(block)) == DEFAULTS


def test_config_template_declared_and_present():
    assert 'template: "specguard-config.template.yml"' in MANIFEST
    assert (EXT_ROOT / "specguard-config.template.yml").is_file()


def test_extensionignore_excludes_dev_only_content():
    patterns = (EXT_ROOT / ".extensionignore").read_text(encoding="utf-8").split()
    for dev_only in ("tests/", "experiments/", "tools/", "docs/implementation_plan.md",
                     "pyproject.toml"):
        assert dev_only in patterns
    assert "docs/" not in patterns  # docs/checks.md ships: reports link to it
    for shipped in ("commands", "scripts", "extension.yml", "README.md", "LICENSE",
                    "docs/checks.md"):
        assert (EXT_ROOT / shipped).exists(), shipped
