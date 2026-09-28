# spec-kit-specguard

A [Spec Kit](https://github.com/github/spec-kit) extension that adds a
**deterministic requirement-quality gate** to spec-driven development: the
same `spec.md` always gets the same verdict, no model is involved in the
verdict, and the gate runs offline on the project's own Python (stdlib only,
3.9+).

Spec Kit's quality mechanisms — `/speckit.checklist`, `/speckit.analyze`, the
self-check inside `/speckit.specify` — are LLM-driven. This extension adds the
missing layer underneath them: a rule-based check you can also run in CI.

Report excerpt (`tests/fixtures/spec_open_marker.md`):

```markdown
## SpecGuard gate: FAIL

`specs/003-account-export/spec.md` · profile `speckit` · 3 FR · 1 SC · 1 user story

Requirements: 3 PASS · 1 WARN · 0 FAIL — Findings: 1 error · 0 warn · 0 info — **Blocking: yes** (fail_on=fail)

| Severity | Check | Where | Detail |
|---|---|---|---|
| error | SK-001 | L26 | Open clarification: file format not specified - JSON, CSV, or both? |

| ID | Line | Gate | Overall | C / S / V | SC class | Smells |
|---|---|---|---|---|---|---|
| FR-002 | L26 | WARN | 0.56 | 0.00 / 1.00 / 0.70 | — | placeholder "NEEDS CLARIFICATION" (high) |
```

## What it checks

| Layer | Checks | Source of the rule |
|---|---|---|
| Requirement wording (FR, SC, NFR) | 11 requirement-smell types — ambiguity, vagueness, subjectivity, optionality, weak modals, non-verifiable verbs, negative statements, baseline-less comparatives, placeholders, missing units, implicit references | SpecGuard core: lexicon method of Femmer et al. 2017, scoring adapted from Zakeri-Nasrabadi et al. 2024 |
| Success criteria | measurability class: QUANTIFIED / BINARY / UNMEASURED | Spec Kit's "Success Criteria Guidelines" |
| Spec structure | open `[NEEDS CLARIFICATION: …]`, unfilled template placeholders, missing mandatory sections, duplicate IDs, stories without priority or Given/When/Then, FRs without MUST/SHALL, … (SK-001…SK-013) | Spec Kit's own "Specification Quality Checklist" and `spec-template.md` |
| spec ↔ tasks | undefined `[US#]` tags and FR references, stories and FRs without tasks, duplicate task IDs (TR-001…TR-006) | links written in `tasks.md` only |

Full catalog, severities and the evidence behind every rule:
[docs/checks.md](docs/checks.md). The report also lists the checklist items
the gate **cannot** check (user value, audience, scope, implementation
details): those stay with `/speckit.checklist`, `/speckit.analyze` or a human.

## Install

```bash
specify extension add --dev /path/to/spec-kit-specguard
```

Requires Spec Kit ≥ 0.14 (verified on 1.0.13.dev0 with the Claude, Copilot
and Gemini integrations) and any Python ≥ 3.9 on the path or in the project
`.venv`. Nothing is pip-installed.

## Use

| Command | What it does |
|---|---|
| `/speckit.specguard.gate [feature-dir]` | Quality gate on `spec.md`; prints the report, stops on a blocking verdict |
| `/speckit.specguard.trace [feature-dir]` | `spec.md` ↔ `tasks.md` traceability |

Hooks registered on install (edit `.specify/extensions.yml` to change):

| Event | Command | Mode |
|---|---|---|
| `after_specify` | gate | optional (asks) |
| `after_clarify` | gate | optional (asks) |
| `before_plan` | gate | **mandatory** — planning stops on a blocking verdict |
| `after_tasks` | trace | optional (asks) |

The agent is instructed to reproduce the report verbatim and to keep any
rewrite suggestions under a separate "Suggestions (LLM, not part of the
verdict)" heading; it edits `spec.md` only when you ask, and re-runs the gate
to confirm a fix.

### CLI and CI

The commands call one script; CI can call it directly:

```bash
python3 .specify/extensions/specguard/scripts/python/run_specguard.py gate specs/001-feature
python3 .specify/extensions/specguard/scripts/python/run_specguard.py trace specs/001-feature --format json
```

| Exit | Meaning |
|---|---|
| 0 | verdict below `--fail-on` (default: only FAIL blocks) |
| 1 | WARN with `--fail-on warn` |
| 2 | FAIL |
| 3 | tool error (spec not found, bad config) — never a verdict |

GitHub Actions step gating every feature spec:

```yaml
- name: SpecGuard gate
  run: |
    rc=0
    for d in specs/*/; do
      python3 .specify/extensions/specguard/scripts/python/run_specguard.py gate "$d" \
        || rc=$(( $? > rc ? $? : rc ))
    done
    exit $rc
```

Without a path the feature is resolved like Spec Kit does it
(`SPECIFY_FEATURE_DIRECTORY`, then `.specify/feature.json`); the extension
never writes `feature.json`.

## Configure

`.specify/extensions/specguard/specguard-config.yml` (created on install),
overridden by `specguard-config.local.yml`, then `SPECKIT_SPECGUARD_<KEY>`
environment variables, then flags:

| Key | Default | Meaning |
|---|---|---|
| `profile` | `speckit` | `speckit` = core + Spec Kit register rules; `default` = SpecGuard core as calibrated on aerospace requirements |
| `fail_on` | `fail` | `fail` / `warn` / `never` |
| `kinds` | `[FR, SC, NFR]` | requirement ID prefixes to assess |
| `write_report` | `false` | also write `specguard-report.{md,json}` into the feature directory |
| `disabled_checks` | `[]` | e.g. `[SK-011, SK-012]` |

## How it works

`spec.md` is parsed tolerantly (formats seen in 187 real specs, see
[experiments](experiments/README.md)); each requirement goes through a
**vendored, hash-locked copy of the SpecGuard core**
(`scripts/python/specguard_speckit/_vendor/specguard_core/VENDOR.json` names
the upstream commit and SHA-256 of every file), then through the `speckit`
profile, then the unchanged gate thresholds (PASS ≥ 0.75 > WARN ≥ 0.50 > FAIL).
Structural findings are combined with requirement gates: any `error` → FAIL,
any `warn` → WARN; `info` never changes the verdict.

This is Layer 1 of SpecGuard's two-layer Quality Agent pattern. Spec Kit's
LLM commands are Layer 2; they explain and propose, the gate decides.

## Limitations (read before relying on it)

- **Lexicon recall is limited.** On SpecGuard's seeded-fault benchmark the core
  detects 0% of smells phrased with vocabulary outside its lexicons and 28.6%
  of blindly written mutations. A PASS means "no deterministic finding", not
  "good spec".
- **Blocking is prompt-level inside the agent.** Spec Kit runs a mandatory
  hook but has no machine-enforced halt on its exit code; the agent is told to
  stop. Use the CI step for hard enforcement.
- **BINARY success criteria can hide subjectivity**: "All users are satisfied"
  counts as a pass/fail predicate. Reported as `SK-010` (info) so a reviewer
  sees every metric-free criterion.
- English only. Calibrated on developer-tooling specs (see experiments); other
  domains may need `profile: default` or new register rules.

## Development

```bash
python -m pytest                          # unit + golden tests, stdlib only
SPECKIT_SOURCE=/path/to/spec-kit python -m pytest tests/test_e2e_speckit.py   # real install
python tools/sync_vendor.py --source ../.. --check   # vendored core == upstream
```

Fix detector bugs upstream in SpecGuard (`src/specguard/core/`), then re-vendor
with `python tools/sync_vendor.py --source <SpecGuard checkout>`.

Plan and design decisions: [docs/implementation_plan.md](docs/implementation_plan.md).

## License

MIT
