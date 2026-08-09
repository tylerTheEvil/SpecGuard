# Edge-extraction annotation guidelines (independent human-annotated subset)

## Purpose and why independence matters

Extraction quality is currently scored against `build_graph` output. For
`MENTIONS` / `REFERS_TO` that reference is **dictionary matching** over the
requirement text (`KNOWN_COMPONENTS` / `KNOWN_STANDARDS`). Scoring an extractor
against a dictionary rewards *reproducing the dictionary*, not recovering the
edges a domain expert would annotate — the circularity a reviewer flagged.

This subset fixes that: it is a **human** reference. Its value is precisely in
the places it disagrees with the dictionary — edges the dictionary **misses**
(entities named by an abbreviation/paraphrase not in the lexicons) and dictionary
matches you **reject** (a token that matches an entity name but is not a real
reference in context). The scorer reports both gaps.

## The one rule that protects independence

**Annotate each requirement by reading its `text`. Do not paste `build_graph`
output.** The `candidate_pool.json` file is an *assist*, not an answer key:
triage it critically. By default the scorer refuses a gold set identical to
the builder reference (`independence_check`): identity is *suspicious* —
consistent with pasted builder output — though not proof of copying, since a
careful annotator can legitimately agree with the dictionary everywhere on a
small subset. If your independently authored set really is identical, re-run
scoring with `--allow-identical`; the report then records
`identical_to_surrogate: true` as a loud caveat that travels with the numbers.

Recommended process per item: (1) read `text` and mark the true edges from your
own understanding; (2) *then* open `candidate_pool.json` for that `req_id` to
catch anything you missed, accepting/rejecting each candidate on its merits.

## Files

- `annotation_template.json` — the file you **fill in**. One entry per sampled
  requirement, each with an empty `edges` list. `inventory` lists the allowed
  target ids (target vocabulary only — not reference edges).
- `candidate_pool.json` — assistive candidates with provenance. `source: "dict"`
  are the builder's dictionary matches (the surrogate — confirm or reject each);
  `source: "surface"` are capitalised identifiers **absent** from the inventory
  that a dictionary-agnostic regex found (possible missing entities — e.g. an ISA
  extension the lexicon lacks). Surface candidates over-generate on purpose and
  include noise; judge each.

## Edge types and decision rules

Each edge you add is an object in an item's `edges` list:

```json
{ "edge_type": "MENTIONS", "target": "CVA6", "evidence_span": "CVA6 shall", "note": "" }
```

- `target` **must** be an id from `inventory` (component id, standard id, or
  requirement id). If you believe the text references a real entity that is *not*
  in the inventory (a dictionary coverage gap), do **not** invent a target id —
  add an edge with `"target": null`, quote the relevant `evidence_span`, and
  describe the entity in `note` (one such entry per distinct unknown entity —
  they do not collapse). The scorer excludes these from P/R/F1 and from
  dictionary-miss pairs and reports them under
  `out_of_inventory_observations` — exactly the coverage evidence we want,
  never scored as matches.
- `evidence_span` must be a **verbatim** substring of `text` that justifies the
  edge (same discipline the extractor's evidence guard enforces).

**MENTIONS** — the requirement names a hardware **component** (target = a
`components` id). Rule: the requirement is *about*, *constrains*, or *directly
refers to* that component. Do **not** annotate a component merely co-occurring in
an example with no requirement bearing on it.

**REFERS_TO** — the requirement cites an external **standard** (target = a
`standards` id): an ISA volume, an interface spec, a RISC-V extension, etc. This
is split from MENTIONS on purpose (P0.1): standards are `REFERS_TO`, components
are `MENTIONS`, matching the builder's typing.

**DERIVES_FROM** — the requirement **refines or depends on another requirement**
(target = a `requirements` id in the subset or the full set). Annotate only a
*local, textually-grounded* refinement (child specialises/constrains the parent),
not a loose thematic link. There is no candidate source for this type — annotate
from scratch. (Compare the 3 hand-built pairs in `builder.HAND_BUILT_DERIVES_FROM`
for the intended granularity.)

Boundary calls worth a `note`: a token that matches a component name but is used
as part of a different proper name; a standard named only inside a
"not applicable" / example clause; an abbreviation whose expansion is the real
entity.

## Finishing and scoring

When done, set in `_meta`: `status` to something other than `TEMPLATE_UNFILLED`
(e.g. `"ANNOTATED"`), `annotator` to your name/initials, and optionally
`annotated_utc`. Then:

```bash
# 1. produce extractor proposals over the subset (any provider), as a JSON list
#    of {source_id, edge_type, target} — e.g. review.export_accepted_edges output
# 2. score against your gold:
python experiments/edge_extraction_human_eval.py score \
    experiments/human_eval/annotation_template.json  proposals.json  \
    --out results/edge_extraction_human_eval.json
```

The report gives, per edge type: P/R/F1 **against the human reference**; the
**surrogate gap** (`dictionary_misses`, `dictionary_false_alarms`); and the
**independence** overlap (Jaccard vs the builder reference). Report the two
non-surrogate numbers — human P/R/F1 and the surrogate gap — in the paper; that
is the honest, non-circular evaluation.

## Scope honesty

This is a small (~20-requirement) subset, single-annotator by default. Report it
as such: it bounds extraction quality on a representative slice and quantifies
the dictionary reference's bias — it is not a full corpus gold standard, and a
second annotator + inter-annotator agreement would strengthen it further.
