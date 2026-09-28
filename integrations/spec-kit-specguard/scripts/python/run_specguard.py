#!/usr/bin/env python3
"""spec-kit-specguard entry point (invoked by the extension's commands and CI).

Usage: run_specguard.py {gate,trace,version} [PATH] [options] — see
specguard_speckit/cli.py. Stdlib-only; runs on the project's own interpreter.
"""

import sys

# Deliberate runtime guard: Spec Kit may pick the project's own (older) interpreter.
if sys.version_info < (3, 9):  # noqa: UP036
    major, minor = sys.version_info[:2]
    sys.stderr.write(f"specguard: error: Python >= 3.9 is required (found {major}.{minor})\n")
    raise SystemExit(3)

from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specguard_speckit.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
