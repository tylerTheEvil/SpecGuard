# Changelog

## [0.1.0] - unreleased

First version, staged in the SpecGuard repository (`integrations/spec-kit-specguard/`).

### Added
- `speckit.specguard.gate`: deterministic requirement-quality gate on `spec.md` —
  vendored SpecGuard core smell detection (11 types), `speckit` register profile
  (P1 entity counts, P2 `any`, P4 `different`, NC clarification markers, P3
  success-criteria outcome register with QUANTIFIED / BINARY / UNMEASURED
  classes), structural checks SK-001…SK-013 codified from Spec Kit's
  specification-quality checklist.
- `speckit.specguard.trace`: `spec.md` ↔ `tasks.md` checks TR-001…TR-006 from
  written links only (`[US#]` tags, FR/SC IDs in task text); severities set
  from 184 real spec/tasks pairs.
- Hooks: `after_specify` / `after_clarify` (optional gate), `before_plan`
  (mandatory gate), `after_tasks` (optional trace).
- CLI `run_specguard.py {gate,trace,version}` with exit codes 0/1/2/3,
  Markdown and JSON output, `--fail-on`, optional report files.
- Layered config (`specguard-config.yml`, `.local.yml`, `SPECKIT_SPECGUARD_*`).
- Vendored core with SHA-256 lock (`VENDOR.json`) and `tools/sync_vendor.py`.
- Tests: parsers, profile (incl. lock-step with the core scorer), structure,
  trace, config, CLI, manifest, vendor lock, pilot-corpus golden, and an
  end-to-end install into a real Spec Kit project.
- Experiments on 187 in-the-wild specs + held-out set (`experiments/`).

### Upstream (SpecGuard core, same change set)
- G6–G9 detector fixes found by the in-the-wild corpus: identifier numerals
  (`FR-036`, `#17`, `Phase 4`) are not missing units; hyphen-compound heads
  (`fail-safe`) and `clean` collocations are not ambiguity; `could not` is not
  a weak modal. Zero delta on CVA6, UAV, the pilot corpus and all seeded-fault
  tiers.
