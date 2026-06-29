# `make_figs.py` — paper figure generator

Regenerates the two paper figures from the prototype's per-requirement report:

- **Fig. 4** — `fig4_smell_distribution.{pdf,svg,png}`: detected smell
  distribution across the CVA6 corpus (horizontal bars, coloured by catalogue
  category, including the non-triggered smell types).
- **Fig. 5** — `fig5_smell_vs_overall.{pdf,svg,png}`: smell count vs. overall
  quality score for the 64 requirements, coloured by gate decision, with the
  linear trend, the gate thresholds (0.50 / 0.75), and the Spearman ρ.

Each figure is written as **vector PDF + SVG** (embed these in Word for crisp
print) and a 300-dpi **PNG** fallback.

## Run

```bash
# one-time: install the [viz] extra (matplotlib; scipy is optional)
pip install -e '.[viz]'

# run from anywhere — default paths resolve relative to the repo root
python scripts/make_figs.py

# or point at a different report / output dir
python scripts/make_figs.py --input results/full_analysis_with_linguistic.json --outdir figures
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--input` | `<repo>/results/full_analysis_with_linguistic.json` | Per-requirement report JSON |
| `--outdir` | `<repo>/figures` | Where the figures are written (created if missing) |

`matplotlib` lives only behind the `[viz]` extra and is never imported from
`src/specguard` (same convention as `coverage_map.py`). `scipy` is optional — a
tie-corrected Spearman fallback is used when it is absent (identical result).

The `figures/` directory is git-ignored: these are regenerated artifacts, not
committed outputs.

## Input format

The script expects the JSON produced by `experiments/run_full_analysis.py`: an
object with a `requirements` list, each item carrying

```jsonc
{
  "smell_report": { "hits": [ { "smell_type": "vagueness" }, ... ], "smell_count": 1 },
  "quality_scores": { "overall": 0.83 },
  "gate_decision": "PASS"          // PASS | WARN | FAIL
}
```

## Tuning the figures

All the knobs are constants near the top of `scripts/make_figs.py` — edit them
there, no CLI flags needed.

| Constant | Controls | Notes |
|----------|----------|-------|
| `FIG4_SIZE`, `FIG5_SIZE` | figure size in inches `(width, height)` | **If an axis label is clipped, widen the figure here** (this is why Fig. 4 is 5.2″ wide). |
| `FIG4_XLABEL`, `FIG5_XLABEL`, `FIG5_YLABEL` | axis label text | Keep Fig. 4's x-label short relative to `FIG4_SIZE[0]` to avoid clipping. |
| `PNG_DPI` | raster export resolution | 300 dpi is print quality; raise for posters. |
| `CAT_COLOR` | bar colours per smell category (Ambiguity / Verifiability / Structural) | Hex strings. |
| `GATE_COLOR`, `GATE_MARK` | Fig. 5 point colour + marker per gate (PASS/WARN/FAIL) | Marker is any matplotlib marker code. |
| `CATEGORY` | maps each of the 11 smell types to its category | Change if the catalogue changes. |
| `plt.rcParams` block | global typography (font family/sizes, axis line width) | Set `font.family` to `"Times New Roman"` (if installed) to match a paper's body text. |

### Common edits

- **A label is cut off on the right** → increase the width in `FIG4_SIZE` /
  `FIG5_SIZE`, or shorten the corresponding `*_XLABEL`. `save_all()` already calls
  `fig.tight_layout()` + saves with `bbox_inches="tight"`, so a wider figure is
  usually all that's needed.
- **Match the paper's font** → set `"font.family": "Times New Roman"` in the
  `plt.rcParams` block (falls back to DejaVu Sans if the font is missing).
- **Bigger text for a slide/poster** → bump `font.size` / `axes.labelsize` in
  `plt.rcParams` and raise `PNG_DPI`.
- **Different gate thresholds** → edit the `for thr in (0.50, 0.75)` loop in
  `fig5_smell_vs_overall`.

## Output

```
figures/
├── fig4_smell_distribution.pdf   # vector — embed in Word
├── fig4_smell_distribution.svg   # vector — editable
├── fig4_smell_distribution.png   # 300-dpi raster
├── fig5_smell_vs_overall.pdf
├── fig5_smell_vs_overall.svg
└── fig5_smell_vs_overall.png
```

The script also prints the smell distribution, the gate counts, and the Spearman
ρ to stdout for a quick sanity check.
