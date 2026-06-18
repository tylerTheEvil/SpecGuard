"""Coverage-map figure for the checkability taxonomy (Contribution #2, Artifact 3).

Reads the taxonomy via the stdlib loader (NO pandas) and renders a stacked bar
chart — one bar per standard family (DO-178C / DO-254 / cross-domain), segments
= machine / screened / human — plus an auditable CSV of the underlying counts so
the figure is reproducible without the PNG.

matplotlib is required and lives only behind the ``[viz]`` extra:
    pip install -e '.[viz]'
    python scripts/coverage_map.py [--calibration] [--path CSV] [--out-dir results]

Honesty guard: the 15 seed objectives were *selected for codifiability*, so a
figure built from them is a CALIBRATION SUBSET, not a representative coverage
result. The guard fires on ``--calibration`` or when the taxonomy has < 30 rows;
it stamps the title and prints a warning so a skewed subset cannot masquerade as
a finding.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from specguard.taxonomy import load_taxonomy, zone_counts_by_standard

_FAMILIES = ("DO-178C", "DO-254", "cross-domain")
_ZONES = ("machine", "screened", "human")
_ZONE_COLORS = {"machine": "#2e7d32", "screened": "#f9a825", "human": "#c62828"}
_CALIBRATION_THRESHOLD = 30
_CALIBRATION_MSG = (
    "CALIBRATION SUBSET — not a representative coverage result; "
    "the 15 objectives were selected for codifiability."
)


def _write_counts_csv(table: dict[str, dict[str, int]], out_csv: Path) -> None:
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["standard", *_ZONES, "total"])
        for fam in _FAMILIES:
            row = table[fam]
            total = sum(row[z] for z in _ZONES)
            writer.writerow([fam, *(row[z] for z in _ZONES), total])


def _render_figure(
    table: dict[str, dict[str, int]], out_png: Path, *, calibration: bool
) -> None:
    import matplotlib

    matplotlib.use("Agg")  # headless / CI
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(_FAMILIES))
    bottoms = [0.0] * len(_FAMILIES)
    totals = [sum(table[fam][z] for z in _ZONES) for fam in _FAMILIES]

    for zone in _ZONES:
        heights = [table[fam][zone] for fam in _FAMILIES]
        bars = ax.bar(
            x, heights, bottom=bottoms, label=zone, color=_ZONE_COLORS[zone], edgecolor="white"
        )
        for i, (h, bar) in enumerate(zip(heights, bars, strict=True)):
            if h and totals[i]:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottoms[i] + h / 2,
                    f"{h}\n({h / totals[i]:.0%})",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white",
                )
        bottoms = [b + h for b, h in zip(bottoms, heights, strict=True)]

    ax.set_xticks(list(x))
    ax.set_xticklabels(_FAMILIES)
    ax.set_ylabel("Codified objectives")
    title = "Checkability coverage by standard"
    if calibration:
        title += "\n" + _CALIBRATION_MSG
    ax.set_title(title, fontsize=11)
    ax.legend(title="zone")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the taxonomy coverage map.")
    parser.add_argument("--path", default=None, help="Taxonomy CSV path (default: auto).")
    parser.add_argument("--out-dir", default="results", help="Output directory (default results/).")
    parser.add_argument(
        "--calibration",
        action="store_true",
        help="Force the calibration-subset warning regardless of row count.",
    )
    args = parser.parse_args(argv)

    rows = load_taxonomy(args.path)
    table = zone_counts_by_standard(rows)
    calibration = args.calibration or len(rows) < _CALIBRATION_THRESHOLD

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "coverage_map.csv"
    out_png = out_dir / "coverage_map.png"

    _write_counts_csv(table, out_csv)
    _render_figure(table, out_png, calibration=calibration)

    if calibration:
        print(f"WARNING: {_CALIBRATION_MSG}", file=sys.stderr)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
