"""Command-line interface — the deterministic tool surface behind the commands.

    run_specguard.py gate  [PATH] [--profile P] [--format md|json] [--fail-on L]
    run_specguard.py trace [PATH] [--format md|json] [--fail-on L]
    run_specguard.py version

PATH is a feature directory or a spec.md file; without it the feature is
resolved like Spec Kit does (SPECIFY_FEATURE_DIRECTORY, .specify/feature.json).

Exit codes:
    0  verdict below the --fail-on threshold (default: only FAIL blocks)
    1  WARN, when --fail-on warn
    2  FAIL
    3  tool error (spec not found, bad config/arguments) — never a verdict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .assess import assess_all
from .config import ConfigError, find_repo_root, load_config
from .featuredir import ResolutionError, resolve_feature
from .model import VERDICT_ORDER, verdict_from
from .parse_spec import DEFAULT_PREFIXES, parse_spec
from .parse_tasks import parse_tasks
from .report import gate_markdown, gate_payload, to_json, trace_markdown, trace_payload
from .structure import NOT_CHECKED, check_structure
from .trace import check_trace

EXIT_TOOL_ERROR = 3
FAIL_ON_THRESHOLD = {"warn": 1, "fail": 2, "never": 99}


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors, which would read as a FAIL verdict."""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_TOOL_ERROR)


def exit_code(verdict: str, fail_on: str) -> int:
    level = VERDICT_ORDER[verdict]
    return level if level >= FAIL_ON_THRESHOLD[fail_on] else 0


def build_parser() -> argparse.ArgumentParser:
    ap = _Parser(prog="run_specguard.py", description="SpecGuard deterministic gate for Spec Kit")
    sub = ap.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("path", nargs="?", help="feature directory or spec.md (default: active "
                       "feature)")
        p.add_argument("--format", choices=("md", "json"), default="md")
        p.add_argument("--fail-on", choices=tuple(FAIL_ON_THRESHOLD), default=None,
                       help="lowest verdict that yields a non-zero exit (default from config: "
                       "fail)")
        p.add_argument("--config", type=Path, default=None,
                       help="config file (default: .specify/extensions/specguard/"
                       "specguard-config.yml + .local.yml)")
        p.add_argument("--write-report", action=argparse.BooleanOptionalAction, default=None,
                       help="also write the report into the feature directory")

    g = sub.add_parser("gate", help="requirement-quality gate on spec.md")
    common(g)
    g.add_argument("--profile", choices=("speckit", "default"), default=None)
    t = sub.add_parser("trace", help="spec.md <-> tasks.md traceability")
    common(t)
    sub.add_parser("version", help="print version and vendored core provenance")
    return ap


def _load(args) -> tuple:
    target = resolve_feature(args.path)
    root = target.repo_root or find_repo_root(Path.cwd())
    cfg, _sources, warnings = load_config(root, explicit=args.config)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if getattr(args, "profile", None):
        cfg["profile"] = args.profile
    if args.fail_on:
        cfg["fail_on"] = args.fail_on
    if args.write_report is not None:
        cfg["write_report"] = args.write_report
    if not target.spec_path.is_file():
        raise ResolutionError(f"spec not found: {target.display(target.spec_path)}")
    return target, cfg


def _prefixes(cfg: dict) -> tuple[str, ...]:
    return tuple(dict.fromkeys(list(DEFAULT_PREFIXES) + cfg["kinds"]))


def _emit(text_md: str, payload_json: str, args, cfg, target, stem: str) -> None:
    sys.stdout.write(payload_json if args.format == "json" else text_md)
    if cfg["write_report"]:
        (target.feature_dir / f"{stem}.md").write_text(text_md, encoding="utf-8")
        (target.feature_dir / f"{stem}.json").write_text(payload_json, encoding="utf-8")
        print(f"report written: {target.display(target.feature_dir / stem)}.{{md,json}}",
              file=sys.stderr)


def run_gate(args) -> int:
    target, cfg = _load(args)
    doc = parse_spec(target.spec_path.read_text(encoding="utf-8"),
                     path=target.display(target.spec_path), prefixes=_prefixes(cfg))
    results = assess_all(doc.requirements, cfg["profile"], tuple(cfg["kinds"]))
    findings = [f for f in check_structure(doc, results)
                if f.check_id not in cfg["disabled_checks"]]
    verdict = verdict_from(findings, [r.gate for r in results])
    code = exit_code(verdict, cfg["fail_on"])
    payload = gate_payload(target, doc, results, findings, verdict, cfg, code != 0, NOT_CHECKED)
    _emit(gate_markdown(payload), to_json(payload), args, cfg, target, "specguard-report")
    return code


def run_trace(args) -> int:
    target, cfg = _load(args)
    if not target.tasks_path.is_file():
        raise ResolutionError(f"tasks.md not found: {target.display(target.tasks_path)} "
                              "(run /speckit.tasks first)")
    prefixes = _prefixes(cfg)
    spec = parse_spec(target.spec_path.read_text(encoding="utf-8"), prefixes=prefixes)
    tasks = parse_tasks(target.tasks_path.read_text(encoding="utf-8"), prefixes=prefixes)
    findings, summary = check_trace(spec, tasks)
    findings = [f for f in findings if f.check_id not in cfg["disabled_checks"]]
    verdict = verdict_from(findings, [])
    code = exit_code(verdict, cfg["fail_on"])
    payload = trace_payload(target, findings, summary, verdict, cfg, code != 0)
    _emit(trace_markdown(payload), to_json(payload), args, cfg, target, "specguard-trace")
    return code


def run_version() -> int:
    from .report import core_provenance

    core = core_provenance()
    print(f"spec-kit-specguard {__version__}")
    print(f"SpecGuard core: {core.get('source_repository')} @ {core.get('source_commit')}"
          f"{' (dirty)' if core.get('source_dirty') else ''}")
    for name, digest in sorted(core.get("files", {}).items()):
        print(f"  {name} sha256={digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "gate":
            return run_gate(args)
        if args.command == "trace":
            return run_trace(args)
        return run_version()
    except (ResolutionError, ConfigError, OSError, UnicodeDecodeError) as exc:
        print(f"specguard: error: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR
