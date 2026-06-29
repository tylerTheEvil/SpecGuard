#!/usr/bin/env python3
"""Regenerate SpecGuard paper figures (Fig. 4 and Fig. 5) from the prototype's
per-requirement report.

Fig. 4: detected smell distribution in the CVA6 corpus (horizontal bar chart,
        colour-coded by catalogue category, including non-triggered types).
Fig. 5: smell count vs overall quality score for the 64 requirements,
        colour-coded by gate decision, with linear trend and gate thresholds.

Outputs each figure as VECTOR (PDF + SVG) and 300-dpi PNG — embed the PDF/SVG in
Word for best print quality.

matplotlib is required and lives only behind the ``[viz]`` extra (same
convention as ``scripts/coverage_map.py``); it is never imported from
``src/specguard``. ``scipy`` is optional (a tie-corrected Spearman fallback is
used when it is absent).

    pip install -e '.[viz]'
    python scripts/make_figs.py [--input REPORT.json] [--outdir DIR]

Default paths resolve relative to the repo root, so the script runs from any
working directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless / CI
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

try:
    from scipy.stats import spearmanr

    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False


# ---- catalogue: 11 smell types, fixed order, mapped to category ----
CATEGORY = {
    "ambiguity": "Ambiguity",
    "vagueness": "Ambiguity",
    "subjectivity": "Ambiguity",
    "implicit_reference": "Ambiguity",
    "comparative": "Ambiguity",
    "optionality": "Verifiability",
    "weakness": "Verifiability",
    "non_verifiable": "Verifiability",
    "negative_statement": "Verifiability",
    "placeholder": "Structural",
    "missing_unit": "Structural",
}
CAT_COLOR = {"Ambiguity": "#E1B84B", "Verifiability": "#D27D84", "Structural": "#8FBF8F"}
GATE_COLOR = {"PASS": "#5BA85B", "WARN": "#E1A33C", "FAIL": "#C0504D"}
GATE_MARK = {"PASS": "o", "WARN": "s", "FAIL": "D"}

# global typography — larger than matplotlib defaults for print legibility
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",  # swap to "Times New Roman" if installed
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "axes.linewidth": 0.8,
    }
)

# ---- tunable figure parameters (see scripts/make_figs.md) ----
# Figure sizes in inches (width, height). Fig. 4 is wide enough that the long
# x-axis label is not clipped; widen further if you lengthen the labels below.
FIG4_SIZE = (5.2, 3.2)
FIG5_SIZE = (4.6, 3.4)
# Axis labels — keep Fig. 4's short relative to FIG4_SIZE width to avoid clipping.
FIG4_XLABEL = "Detected events (N = 12, corpus of 64)"
FIG5_XLABEL = "Smell count per requirement"
FIG5_YLABEL = "Overall quality score"
PNG_DPI = 300  # raster export resolution


def _repo_root() -> Path:
    """Locate the repo root by searching upward for ``pyproject.toml``."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def load(path: str | Path) -> list[dict]:
    d = json.loads(Path(path).read_text())
    return d["requirements"]


def smell_count(rec: dict) -> int:
    sr = rec["smell_report"]
    return sr.get("smell_count", len(sr.get("hits", [])))


def save_all(fig, outdir: str | Path, stem: str) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()  # reposition axes so no label overflows the canvas
    fig.savefig(outdir / f"{stem}.pdf", bbox_inches="tight")  # vector — best for print
    fig.savefig(outdir / f"{stem}.svg", bbox_inches="tight")  # vector — editable
    fig.savefig(outdir / f"{stem}.png", dpi=PNG_DPI, bbox_inches="tight")  # raster fallback
    plt.close(fig)


def fig4_smell_distribution(reqs: list[dict], outdir: str | Path) -> dict[str, int]:
    counts = dict.fromkeys(CATEGORY, 0)
    for r in reqs:
        for h in r["smell_report"].get("hits", []):
            t = h.get("smell_type")
            if t in counts:
                counts[t] += 1
    # order: triggered first (desc), then non-triggered
    order = sorted(counts, key=lambda k: (-counts[k], k))
    labels = order
    values = [counts[k] for k in order]
    colors = [CAT_COLOR[CATEGORY[k]] for k in order]

    fig, ax = plt.subplots(figsize=FIG4_SIZE)
    y = np.arange(len(labels))[::-1]  # top-to-bottom = highest first
    ax.barh(y, values, color=colors, edgecolor="#444444", linewidth=0.5, height=0.7)
    for yi, v in zip(y, values, strict=True):
        ax.text(v + 0.08, yi, str(v), va="center", ha="left", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel(FIG4_XLABEL)
    ax.set_xlim(0, max(values) + 1)
    ax.spines[["top", "right"]].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CAT_COLOR.values()]
    ax.legend(handles, CAT_COLOR.keys(), loc="lower right", frameon=False)
    save_all(fig, outdir, "fig4_smell_distribution")
    return counts


def fig5_smell_vs_overall(reqs: list[dict], outdir: str | Path) -> tuple[float, dict[str, int]]:
    x = np.array([smell_count(r) for r in reqs], dtype=float)
    y = np.array([r["quality_scores"]["overall"] for r in reqs], dtype=float)
    gates = [r["gate_decision"] for r in reqs]

    if _HAVE_SCIPY:
        rho, _ = spearmanr(x, y)
    else:  # tie-corrected Spearman fallback

        def rank(a):
            order = np.argsort(a, kind="mergesort")
            r = np.empty(len(a))
            r[order] = np.arange(1, len(a) + 1)
            for v in np.unique(a):  # average ties
                idx = np.where(a == v)[0]
                r[idx] = r[idx].mean()
            return r

        rx, ry = rank(x), rank(y)
        rho = np.corrcoef(rx, ry)[0, 1]

    fig, ax = plt.subplots(figsize=FIG5_SIZE)
    # small horizontal jitter so overlapping points at integer x are visible
    rng = np.random.default_rng(0)
    jit = (rng.random(len(x)) - 0.5) * 0.12
    counts = {}
    for g in ("PASS", "WARN", "FAIL"):
        m = [i for i, gg in enumerate(gates) if gg == g]
        counts[g] = len(m)
        ax.scatter(
            x[m] + jit[m],
            y[m],
            s=34,
            c=GATE_COLOR[g],
            marker=GATE_MARK[g],
            edgecolors="#333333",
            linewidths=0.4,
            alpha=0.9,
            zorder=3,
        )
    # linear trend line
    b, a = np.polyfit(x, y, 1)
    xs = np.linspace(x.min() - 0.2, x.max() + 0.2, 50)
    ax.plot(xs, b * xs + a, "--", color="#666666", linewidth=1.0, zorder=2)
    # gate thresholds
    for thr in (0.50, 0.75):
        ax.axhline(thr, ls=":", color="#999999", linewidth=0.9, zorder=1)
        ax.text(
            x.max() + 0.05,
            thr + 0.005,
            f"{thr:.2f}",
            fontsize=8,
            color="#777777",
            va="bottom",
            ha="right",
        )
    ax.set_xlabel(FIG5_XLABEL)
    ax.set_ylabel(FIG5_YLABEL)
    ax.set_xlim(-0.3, x.max() + 0.4)
    ax.set_ylim(0.0, 1.05)
    ax.spines[["top", "right"]].set_visible(False)
    legend_items = [
        Line2D(
            [0],
            [0],
            marker=GATE_MARK[g],
            color="none",
            markerfacecolor=GATE_COLOR[g],
            markeredgecolor="#333333",
            markersize=7,
            label=f"{g} (n={counts[g]})",
        )
        for g in ("PASS", "WARN", "FAIL")
    ]
    leg = ax.legend(handles=legend_items, loc="lower left", frameon=True, framealpha=0.9)
    leg.get_frame().set_edgecolor("#cccccc")
    ax.text(
        0.97,
        0.04,
        rf"Spearman $\rho$ = {rho:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#cccccc"},
    )
    save_all(fig, outdir, "fig5_smell_vs_overall")
    return rho, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Regenerate SpecGuard paper figures (Fig. 4 / 5).")
    ap.add_argument(
        "--input",
        default=None,
        help="Per-requirement report JSON (default: results/full_analysis_with_linguistic.json).",
    )
    ap.add_argument("--outdir", default=None, help="Output directory (default: figures/).")
    args = ap.parse_args(argv)

    root = _repo_root()
    default_input = root / "results" / "full_analysis_with_linguistic.json"
    input_path = Path(args.input) if args.input else default_input
    outdir = Path(args.outdir) if args.outdir else root / "figures"

    reqs = load(input_path)
    counts = fig4_smell_distribution(reqs, outdir)
    rho, gate_counts = fig5_smell_vs_overall(reqs, outdir)

    triggered = {k: v for k, v in counts.items() if v}
    print(f"Loaded {len(reqs)} requirements")
    print(f"Fig. 4 smell distribution: {triggered}")
    print(f"Fig. 5 gate counts: {gate_counts}")
    print(f"Fig. 5 Spearman rho (smell count vs overall): {rho:.3f}")
    print(f"Figures written to: {outdir.resolve()} (.pdf, .svg, .png)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
