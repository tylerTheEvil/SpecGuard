"""Load the checkability taxonomy CSV into :class:`TaxonomyRow` records.

Stdlib-only (uses :mod:`csv`, no pandas). The CSV at ``taxonomy/`` in the repo
root is the human-editable source of truth; this loader reads and never writes.
"""

from __future__ import annotations

import csv
from pathlib import Path

from specguard.taxonomy.schema import COLUMNS, TaxonomyRow

_DEFAULT_RELPATH = Path("taxonomy") / "checkability_taxonomy.csv"


def _find_default_path() -> Path:
    """Search upward (from this module, then cwd) for the taxonomy CSV.

    Resolving relative to the package keeps it working under an editable
    install regardless of the process working directory.
    """
    starts = [Path(__file__).resolve(), Path.cwd().resolve()]
    seen: set[Path] = set()
    for start in starts:
        for parent in [start, *start.parents]:
            if parent in seen:
                continue
            seen.add(parent)
            candidate = parent / _DEFAULT_RELPATH
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        f"Could not locate {_DEFAULT_RELPATH} by searching upward from "
        f"{starts[0]} or the working directory. Pass an explicit path."
    )


def load_taxonomy(path: str | Path | None = None) -> list[TaxonomyRow]:
    """Parse the taxonomy CSV into rows.

    Args:
        path: explicit CSV path; if ``None``, the default is located by
            searching upward for ``taxonomy/checkability_taxonomy.csv``.

    Returns:
        One :class:`TaxonomyRow` per data row. Blank rows and ``#``-commented
        rows (``objective_id`` empty or starting with ``#``) are skipped so a
        template/placeholder file loads cleanly.

    Raises:
        FileNotFoundError: if no CSV can be located.
        ValueError: if the header does not match the expected columns.
    """
    csv_path = Path(path) if path is not None else _find_default_path()
    rows: list[TaxonomyRow] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or tuple(reader.fieldnames) != COLUMNS:
            raise ValueError(
                f"Unexpected CSV header in {csv_path}.\n"
                f"  expected: {COLUMNS}\n"
                f"  found:    {tuple(reader.fieldnames or ())}"
            )
        for raw in reader:
            obj_id = (raw.get("objective_id") or "").strip()
            if not obj_id or obj_id.startswith("#"):
                continue
            rows.append(TaxonomyRow(**{col: (raw.get(col) or "").strip() for col in COLUMNS}))
    return rows
