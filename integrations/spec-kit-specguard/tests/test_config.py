"""Config layering and the flat-YAML reader."""

from __future__ import annotations

import pytest
from specguard_speckit.config import (
    DEFAULTS,
    ConfigError,
    find_repo_root,
    load_config,
    parse_flat_yaml,
)


def test_parse_flat_yaml_forms():
    data = parse_flat_yaml(
        "# comment\nprofile: default   # trailing\nfail_on: 'warn'\nkinds: [FR, SC]\n"
        "write_report: true\ndisabled_checks:\n  - SK-011\n  - SK-012\n"
    )
    assert data == {"profile": "default", "fail_on": "warn", "kinds": ["FR", "SC"],
                    "write_report": True, "disabled_checks": ["SK-011", "SK-012"]}


def test_parse_rejects_nested_mappings():
    with pytest.raises(ConfigError):
        parse_flat_yaml("gate:\n  profile: default\n")


def test_template_parses_to_defaults(tmp_path):
    from conftest import EXT_ROOT

    text = (EXT_ROOT / "specguard-config.template.yml").read_text(encoding="utf-8")
    assert parse_flat_yaml(text) == DEFAULTS


def _project(tmp_path, config: str | None = None, local: str | None = None):
    base = tmp_path / ".specify" / "extensions" / "specguard"
    base.mkdir(parents=True)
    if config is not None:
        (base / "specguard-config.yml").write_text(config, encoding="utf-8")
    if local is not None:
        (base / "specguard-config.local.yml").write_text(local, encoding="utf-8")
    return tmp_path


def test_layering_project_local_env(tmp_path):
    root = _project(tmp_path, "fail_on: warn\nprofile: default\n", "profile: speckit\n")
    cfg, sources, warnings = load_config(root, env={"SPECKIT_SPECGUARD_KINDS": "fr, sc"})
    assert cfg["fail_on"] == "warn"          # project
    assert cfg["profile"] == "speckit"       # local overrides project
    assert cfg["kinds"] == ["FR", "SC"]      # env overrides, normalized
    assert sources[0] == "defaults" and sources[-1] == "environment" and warnings == []


def test_invalid_choice_rejected(tmp_path):
    root = _project(tmp_path, "fail_on: sometimes\n")
    with pytest.raises(ConfigError, match="fail_on"):
        load_config(root, env={})


def test_unknown_key_warns_not_ignored_silently(tmp_path):
    root = _project(tmp_path, "fail-on: warn\n")
    cfg, _, warnings = load_config(root, env={})
    assert cfg["fail_on"] == "fail"
    assert warnings and "fail-on" in warnings[0]


def test_env_bool(tmp_path):
    cfg, _, _ = load_config(_project(tmp_path), env={"SPECKIT_SPECGUARD_WRITE_REPORT": "true"})
    assert cfg["write_report"] is True


def test_find_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECIFY_INIT_DIR", raising=False)
    root = _project(tmp_path)
    nested = root / "specs" / "001"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == root.resolve()
