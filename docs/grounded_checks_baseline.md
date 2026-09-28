# Initial state and verification record

Task branch: `codex/grounded-requirements-checks`.
Starting commit: `0f4a3057a1bf2800249558c484220ca5093ed091`; initial tree clean.
No AGENTS.md was found in the repository/ancestor search. CLAUDE.md was read.
No publication, push, manuscript edit or working database mutation was performed.

## Initial observations

The system Python 3.14 had no pytest. A local Python 3.12.13 `.venv` with the
project dev/graph extras resolved this environment issue. Before production
changes: `pytest -q -m 'not neo4j'` → **243 passed, 8 skipped, 32 deselected**.

Four regressions were added and run before production edits: **4 failed**:
empty runner gave PASS; zero checks gave 100%; timing query used `coalesce(b, 0)`
and lacked a composition declaration; a user text requirement received mock
DAL/verification metadata in TraceabilityAgent. After P0: **4 passed**.

The preserved `results/grounded_checks/baseline.json` records two requirements
with RUN / ENABLE=1 and RUN / ENABLE=0: both text gates PASS, consistency heuristic
1.0. A nominal sensor requirement without a loss reaction also passed. Changing
its text after evidence approval had no dedicated freshness mechanism. These
were gaps in supported analysis, not proof that the score formula was defective.

Code inspection confirmed Q14's first-15 topology screening (already correctly
labeled screening in architecture notes); duplicated mock graph logic; mismatched
Hazard/SafetyHazard labels; and clear-before-load Neo4j fixtures/loaders. Safe
MERGE-based CLI import already existed and was preserved.

## Acceptance checks

See the task's final report and generated validation logs for actual final
counts. The dedicated suite covers scoped PASS/FAIL/UNKNOWN/N/A/ERROR, stale
historical evidence, mixed-status aggregation, additive timing/units, reviewed
scenarios/assumptions, strict static contract semantics, source hashes, pair
limits, CLI import/report/exit codes, and memory/Neo4j snapshot adapter equivalence.

Live Neo4j parity is a separate opt-in integration test. During local work the
Docker executable existed but its daemon was unavailable; no isolated Neo4j
service was available. No user database was contacted as a substitute. Skipped
Neo4j tests are not evidence of database compatibility. Optional linguistic/live
provider paths similarly require their own environments/services.

## Final local results (Python 3.12.13)

- Full pytest: **297 passed, 40 skipped**. Of the skipped checks, 32 require an
  isolated Neo4j target and 8 require optional textstat/spaCy/matplotlib packages.
  The 53 dedicated P0/P1/P2/regression tests pass, including CLI subprocesses and
  an actual archived-baseline replay. See `results/grounded_checks/test_results.txt`.
- `ruff check .`: passed. New modules/tests/example runner are formatted. The
  repository-wide format check remains informational with pre-existing style
  differences; the original commit itself reports 48 files needing formatting.
  No new files requiring formatting relative to that baseline are left.
- `mypy src/specguard/verification --follow-imports=silent`: all 6 modules pass.
  Full-project mypy remains non-green: 10 existing issues vs 11 on archived
  baseline in the same environment (optional imports/stubs and existing parser,
  provider, extraction, CLI and graph return annotations). Both logs are saved;
  no new type error remains.
- `python -m build --no-isolation`: sdist and wheel built successfully.
- `python -S` import/analysis of the full synthetic bundle: passed without
  site-packages. `specguard taxonomy validate`: 15 rows, 0 errors.
- Legacy compliance demo executes with explicit UNKNOWN scope; structured CLI
  returns exit 2 for the deliberate example violations, as documented.
- No live Neo4j/LLM calls or optional linguistic benchmark were used as substitutes
  for skipped checks. CI has a separately guarded Neo4j integration path.

Before/after: the original empty graph reports 100% PASS; the new runner reports
UNKNOWN and a null evaluated fraction. The two reviewed RUN/ENABLE guarantees
now yield a P2-PAIR FAIL. The synthetic combined report contains 8 PASS, 2 FAIL,
3 UNKNOWN, 0 N/A, 0 ERROR and 1 STALE (one historical PASS); current completed
checks are 9/13. Scenario required-field coverage is 4/5 reviewed applicable
scenarios, not a claim of exhaustive hazard coverage or system reliability.
