# PR #1 review and branch integration

Reviewed PR: <https://github.com/tylerTheEvil/SpecGuard/pull/1>.
Review date: 2026-09-28.
Merged main commit: `2acf02176ce79283b4fafa82e4bb51c645c77732`.
Feature branch: `codex/grounded-requirements-checks`.
Rebased feature commit: `4949821edf31b603fbd552cf1d7e6662c1e3aad9`.

The rebase completed without textual conflicts. The extension's byte-exact
vendor check then detected the feature branch's changes to scorer documentation.
Re-running `integrations/spec-kit-specguard/tools/sync_vendor.py --source .`
from the repository root synchronized
the scorer and its provenance/hash lock. No scoring formula or threshold changed.
A separate CI job now runs extension unit/golden tests and vendor checks on
Python 3.9 and 3.12; root pytest does not discover this nested suite.

## Open review findings

Follow-up (2026-09-28): both findings below are fixed on
`codex/fix-compounds-fences-ci`, with regression tests. The original review and
its validation record are retained below.

These two findings were reproduced locally and are not fixed by the integration
commit. They concern behavior introduced in PR #1, independently of the rebase.

### P2: Unrecognized hyphen prefixes suppress ambiguous words

In `src/specguard/core/smell_detector.py`, `_is_technical_use` treats every
hyphenated prefix outside the short `INTENSIFIER_PREFIXES` list as technical.
`detect_ambiguity("The search shall be fast.")` reports `fast`, but
`detect_ambiguity("The search shall be lightning-fast.")` returns an empty list.
The requirement still lacks a measurable performance bound, so the new exception
removes a valid warning. The extension inherits this behavior through its vendor.
Limit the exception to recognized technical compounds such as `fail-safe` and
add a regression for unknown subjective compounds such as `lightning-fast`.

### P2: Nested Markdown fences leak example requirements

In `integrations/spec-kit-specguard/scripts/python/specguard_speckit/parse_spec.py`,
`_visible_lines` toggles a boolean at every triple-backtick/tilde prefix without
tracking the opening fence's character or length. For this valid Markdown:

~~~~~markdown
````markdown
```python
- **FR-999**: The system shall be fast.
```
````
## Requirements
- **FR-001**: The system shall respond within 10 ms.
~~~~~

`parse_spec(text).requirements` returns both `FR-999` (line 3) and `FR-001`
(line 7). Only `FR-001` is a real requirement; the other is inside a fenced
example and may introduce spurious quality/duplicate-ID findings. Track the
opening fence character and run length, and close only on a matching valid
closing fence of at least that length. Cover nested and mixed fence characters.

## Local validation after rebase

Python 3.12.13:

- Root `pytest -q`: **309 passed, 40 skipped**. Skips retain the prior environment
  limitations: 32 isolated Neo4j checks and 8 optional dependency checks.
- Extension `pytest -q` from its directory: **132 passed, 1 skipped module**.
  Live Spec Kit installation E2E was skipped because `specify` / `SPECKIT_SOURCE`
  was unavailable; this is not a successful E2E run.
- `integrations/spec-kit-specguard/tools/sync_vendor.py --source . --check`: passed.
- `ruff check . --extend-exclude .claude/worktrees`: passed.
- `git diff --check`: passed.
- `python -m build --no-isolation`: sdist and wheel built successfully.
- Replayed all 10 synthetic cases in all three configurations to a temporary
  directory: case-set hash and every case result matched the archived exports.
  Historical result files and the original baseline record were preserved.

The new CI matrix was configured but not run on GitHub as part of this local
review. Python 3.9, live Neo4j and live Spec Kit E2E were not run locally.
