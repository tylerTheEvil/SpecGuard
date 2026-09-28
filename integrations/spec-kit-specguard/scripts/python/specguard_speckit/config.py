"""Configuration with Spec Kit's documented layering.

1. built-in defaults (mirrored in extension.yml ``defaults``)
2. ``.specify/extensions/specguard/specguard-config.yml``      (project, committed)
3. ``.specify/extensions/specguard/specguard-config.local.yml`` (local, gitignored)
4. environment ``SPECKIT_SPECGUARD_<KEY>``
5. command-line flags

The config is flat, so a minimal YAML subset reader suffices and keeps the
package stdlib-only: ``key: value`` with scalars, ``[a, b]`` flow lists and
``- item`` block lists, ``#`` comments. Anything richer is rejected loudly.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

EXT_ID = "specguard"
CONFIG_NAME = "specguard-config.yml"
LOCAL_CONFIG_NAME = "specguard-config.local.yml"
ENV_PREFIX = "SPECKIT_SPECGUARD_"

DEFAULTS: dict = {
    "profile": "speckit",
    "fail_on": "fail",
    "kinds": ["FR", "SC", "NFR"],
    "write_report": False,
    "disabled_checks": [],
}
CHOICES = {
    "profile": ("speckit", "default"),
    "fail_on": ("fail", "warn", "never"),
}
LIST_KEYS = ("kinds", "disabled_checks")
BOOL_KEYS = ("write_report",)


class ConfigError(ValueError):
    pass


def _scalar(value: str):
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if ch in "\"'":
            quote = None if quote == ch else (quote or ch)
        elif ch == "#" and quote is None and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def parse_flat_yaml(text: str, source: str = "<config>") -> dict:
    data: dict = {}
    pending_list: str | None = None
    for no, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if pending_list and re.match(r"^\s+-\s*", line):
            data[pending_list].append(_scalar(re.sub(r"^\s+-\s*", "", line)))
            continue
        pending_list = None
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m or line[0].isspace():
            raise ConfigError(f"{source}:{no}: unsupported YAML (flat 'key: value' only): {raw!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            data[key] = []
            pending_list = key
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [_scalar(x) for x in inner.split(",")] if inner else []
        else:
            data[key] = _scalar(value)
    return data


def find_repo_root(start: Path) -> Path | None:
    """Nearest ancestor containing ``.specify/`` (or SPECIFY_INIT_DIR)."""
    env = os.environ.get("SPECIFY_INIT_DIR")
    if env and (Path(env) / ".specify").is_dir():
        return Path(env).resolve()
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".specify").is_dir():
            return candidate
    return None


def _validate(cfg: dict, source: str) -> None:
    for key, choices in CHOICES.items():
        if key in cfg and cfg[key] not in choices:
            raise ConfigError(f"{source}: {key} must be one of {', '.join(choices)}, "
                              f"got {cfg[key]!r}")
    for key in LIST_KEYS:
        if key in cfg and not isinstance(cfg[key], list):
            cfg[key] = [cfg[key]]
    for key in BOOL_KEYS:
        if key in cfg and not isinstance(cfg[key], bool):
            raise ConfigError(f"{source}: {key} must be true or false, got {cfg[key]!r}")


def load_config(repo_root: Path | None, explicit: Path | None = None,
                env: dict | None = None) -> tuple[dict, list[str], list[str]]:
    """Merge the layers; return (config, sources used, warnings)."""
    env = os.environ if env is None else env
    cfg = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    sources = ["defaults"]
    warnings: list[str] = []

    files: list[Path] = []
    if explicit is not None:
        files.append(explicit)
    elif repo_root is not None:
        base = repo_root / ".specify" / "extensions" / EXT_ID
        files += [base / CONFIG_NAME, base / LOCAL_CONFIG_NAME]
    for path in files:
        if not path.is_file():
            if explicit is not None:
                raise ConfigError(f"config file not found: {path}")
            continue
        layer = parse_flat_yaml(path.read_text(encoding="utf-8"), str(path))
        _validate(layer, str(path))
        unknown = sorted(k for k in layer if k not in DEFAULTS)
        if unknown:
            warnings.append(f"{path}: ignored unknown key(s): {', '.join(unknown)} "
                            f"(known: {', '.join(DEFAULTS)})")
        cfg.update({k: v for k, v in layer.items() if k in DEFAULTS})
        sources.append(str(path))

    env_layer: dict = {}
    for key in DEFAULTS:
        raw = env.get(ENV_PREFIX + key.upper())
        if raw is None:
            continue
        if key in LIST_KEYS:
            env_layer[key] = [x.strip() for x in raw.split(",") if x.strip()]
        else:
            env_layer[key] = _scalar(raw)
    if env_layer:
        _validate(env_layer, "environment")
        cfg.update(env_layer)
        sources.append("environment")

    cfg["kinds"] = [str(k).upper() for k in cfg["kinds"]]
    cfg["disabled_checks"] = [str(c).upper() for c in cfg["disabled_checks"]]
    return cfg, sources, warnings
