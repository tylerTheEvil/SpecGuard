# Novelty Deepening — Four Directions, Literature-Checked

> Working research document. Created 2026-06-10 from four parallel literature
> sweeps (web search, 2014–2026 coverage) stress-testing each proposed
> contribution against the closest prior art. Each direction below survives
> as novel, with the precise surviving claim, the landmine papers a reviewer
> will raise, and the differentiation that answers them.
>
> **Caveat:** citation identifiers (arXiv IDs, DOIs) were gathered by
> automated search on 2026-06-10. Verify every reference against the actual
> paper before it enters a manuscript.

The common upgrade pattern across all four: move from *"we built an
instance"* to *"we defined a method/property and the instance demonstrates
it."*

---

## Direction 1 — Regulatory codification methodology with a coverage boundary

**Upgrades novelty #3** from "15 hand-written Cypher objectives" to a
*method*.

### Surviving claim

> No prior work (a) enumerates and classifies all DO-178C (~71) and DO-254
> (~50) objectives by **checkability class** (structural / traceability /
> numerical-consistency / coverage / not-machine-checkable); (b) derives
> **graph-pattern templates** per class for executable compliance checking;
> (c) publishes a quantitative **coverage map** of the codifiable fraction
> of each standard; or (d) defines **cross-domain compliance bindings**
> linking DO-178C software objectives with DO-254 hardware objectives in a
> unified knowledge graph. The cross-domain SW↔FPGA binding has no
> precedent (re-confirmed by independent search: RACK/ARCOS is explicitly
> software-only).

### What to build

1. Classify all 71+50 objectives into the five checkability classes
   (classification only — NOT codification; weeks, not the forbidden 700h).
2. One graph-pattern template per checkable class; show the existing 15
   objectives are instances.
3. The coverage map as a quantitative artifact ("X% structural, Y%
   traceability, ..., Z% inherently human").
4. Formalize the graph **meta-model**: the minimal node/edge ontology
   certification evidence must be expressed in for the templates to be
   expressible (position as complementary to OMG SACM — SACM models
   argument structure; this models regulatory-objective codification).

### Landmines and differentiation

| Paper | What it is | Differentiation |
|---|---|---|
| **RACK / ARCOS** (GE/Galois; SAFECOMP-W 2023, DASC 2023/2024) — *the* landmine | Semantic triplestore curating SW certification evidence, DO-178C compliance dashboards, $10.5M DARPA program | RACK curates *evidence* against existing objectives; contributes no checkability taxonomy, no coverage map, no templates, and **no DO-254** (ARCOS = "...Certification of *Software*"). SpecGuard contributes the taxonomy, the DO-254 extension, and the cross-domain binding — different layers. Must be cited and differentiated explicitly. |
| Cartile et al. (Aerospace MDPI 2025/2026) | Ontology design patterns for regulatory *guidance material* (ARP4754B text) | Models how regulations are written, not the objective tables (what must be demonstrated). Cite + distinguish. |
| Métayer & Paz (IEEE 2019) | DAL-sensitive UML DSL of DO-178C objective structure | SW-only UML profile; no checkability classes, no coverage map, no graph patterns. |
| Holloway, *Explicate '78* (NASA TM-2014-218282) | Reconstructs DO-178C's implicit assurance argument | Foundational "make the structure explicit" prior work; extend with DO-254 + taxonomy + executability. |
| OMG SACM v2.2; OntoGSN (2025) | Assurance-case meta-models | Argument-structure-centric, not regulatory-objective-centric. Complementary, cite. |

**Honest scoping:** applying graph/semantic-web tech to certification
evidence is NOT new (RACK, ISWC 2023, EMERALD). The taxonomy, coverage map,
templates, and cross-domain binding are the new layers.

**Effort:** ~3–5 weeks (classification + templates + meta-model writeup).
**Target:** dissertation spine + Paper #3 core section; coverage map is a
standalone figure reviewers remember.

---

## Direction 2 — Verified non-interference property + GSN assurance case

**Sharpens novelty #2** from "we designed the LLM to be augmentative" to a
*stated, enforced, and verified property* with an assurance argument.

### Surviving claim

> First formalized **non-interference property** (in the Goguen–Meseguer
> sense: no information flow from any `ModelProvider` output into any
> deterministic verdict) for LLM integration in qualification-candidate
> development tools under DO-330 — enforced **architecturally** (not
> probabilistically), verified via **property-based tests**, and argued via
> a **GSN assurance case** establishing TQL-5 qualifiability. No prior work
> combines all four elements; the Simplex-architecture analogy has been
> claimed only for runtime control systems, never for development tools.

### What to build

1. Formal statement of the property over the tool surface (gate, scores,
   compliance verdicts vs. provider outputs).
2. Verification: extend the existing payload-equality tests into systematic
   property-based tests + a static information-flow argument (provider
   types unreachable from decision paths).
3. GSN assurance case for the TQL-5 claim, with evidence nodes pointing at
   the actual test artifacts (inherit AMLAS patterns, state the extension).

### Landmines and differentiation

| Paper | What it is | Differentiation |
|---|---|---|
| **Liu et al. (DASC 2025, Collins/Loonwerks)** — closest on DO-330 | Argues ML-based support tools are *admissible* at TQL-5 (Criterion 3) | Argues admissibility by analogy, provides **no mechanism**. SpecGuard provides the structural mechanism that makes the analogy hold. Complementary, not colliding — cite prominently. |
| Habli et al., *BIG Argument* (York 2025); AMLAS (2021) | GSN safety-case frameworks for AI systems | *Behavioral* safety of deployed AI systems; not tool qualification, not structural isolation. Inherit AMLAS patterns, state the extension. |
| Nesti et al. (2025) | Simplex architecture for deep-learning *control systems* (hypervisor isolation) | Runtime control domain, hardware isolation, no formal property, no DO-330/GSN. The dev-tool domain is unclaimed. |
| Bhattarai & Vu (2026) | Goguen–Meseguer-framed information-flow control for LLM *agents* | Agent-security threat model (prompt injection); orthogonal to tool qualification. |
| EASA AI Concept Paper Issue 2 (2023); FAA AI Roadmap v1 (2024) | Regulatory framing | Both address airborne/deployed AI; neither addresses LLM-containing *development tools* — this negative space IS the gap. Anchor citations. |

**Effort:** ~2–4 weeks (formalization + tests exist in embryo + GSN case).
**Target:** defense-winning formalization; opens SAFECOMP/EDCC as venues
beyond RE conferences.

---

## Direction 3 — Deterministic semantic-drift guard for LLM requirement rewrites

**Best practical novelty**; completes the guard symmetry (every LLM output
channel gets a deterministic guard: explanation→non-interference,
edges→evidence spans, rewrites→drift guard).

### Surviving claim

> Existing LLM requirements-improvement work relies exclusively on human
> acceptance as the semantic-preservation mechanism (Veizaga et al. TSE
> 2024 — CNL substitutions, no verifier; Dieste et al. REFSQ 2026 —
> *acknowledges* meaning drift empirically, offers no guard; QVscribe and
> IBM RQA — score-and-suggest, human-only safety net). No system applies
> automated deterministic post-generation invariant verification before a
> rewrite reaches the engineer, and no study quantifies drift frequency by
> invariant class. Modal-verb weakening as an automatically detectable
> drift class is unmeasured anywhere.

### What to build

Invariant checker diffing draft vs. original: requirement ID unchanged;
numeric values + units preserved; referenced entities preserved (reuse the
extraction inventory); modal verb never weakened (shall ↛ should/may); no
new entities introduced. Wire into `/sg-refine` before any draft is shown.
Experiment: N LLM rewrites, measure per-invariant violation rates with and
without the guard.

### Landmines and pre-emptions

- **"Isn't this Paska with LLMs?"** — Paska emits structurally bounded CNL
  pattern substitutions with no invariant verifier; this guards *free-text
  LLM rewrites* and adds a new architectural layer, in a regulated domain
  Paska does not claim.
- **"Use NLI entailment instead (SummaC-style)."** — NLI models are
  probabilistic and not DO-330-qualifiable as detection logic; the
  deterministic guard is a regulatory-driven architectural choice. Cite and
  distinguish SummaC/QAFactEval/SemEval-2024 Task 2 as adjacent methods.
- **"Humans in the loop suffice."** — Dieste et al. show drift exists under
  human review; ideally show quantitatively that the guard catches drift
  classes humans miss under time pressure (links to the planned user study).
- **Scope precision:** claim preservation of a *finite, defined invariant
  set* — never full semantic equivalence (that would require formal
  methods and invite an SMT objection).
- **OPEN ACTION:** AirReq (IEEE REW 2025) semantic-preservation stance is
  unknown — fetch and check before any paper claims this gap in print.
  This is the one unverified overlap risk.

**Effort:** days (the pieces exist: parser, entity inventory, lexicons) +
a small experiment. **Target:** immediately publishable (NLP4RE/REFSQ
short paper or Paper #3 section); also a real product-grade safety feature.

---

## Direction 4 — Flagship experiment: CVA6 spec vs. RISC-V ISA standard

**Demonstrates the cross-domain/consistency machinery on two real,
independently authored documents** — answering the "your UAV dataset is
authored" objection at the root.

### Surviving claim

> RISC-V conformance tooling (RISCOF, riscv-arch-test, Sail) verifies
> behavior at the binary/formal-model level — confirmed, none operate on
> natural-language requirements. NL consistency work (ALICE 2024, pairwise
> classifiers) is intra-corpus. The closest structural analogues (RFC-vs-
> TCP/IP gap mining 2025; SPECA/Ethereum 2026) anchor one side in *code*.
> No prior work performs NL-requirements-level cross-document consistency
> between an implementation spec and its governing standard, mining typed
> hardware entities (CSRs, ISA extensions, exception behaviors, version
> references) into a knowledge graph with coherence checks.

### Why it is feasible (verified)

- CVA6 spec pins exact ISA versions (User-Level 20191213, Privileged
  20211203) → concrete version-reference checks.
- **Ground-truth smoking gun exists:** CVA6 documents a real deviation from
  the privileged spec (no illegal-instruction exception on writes of
  unsupported values to WLRL CSR fields). No automated NL-level process
  detected it. The experiment should *recover this known deviation* — a
  built-in validity check.
- The RISC-V NL spec's ambiguities are independently documented (Reid's
  analyses; spec GitHub issues) — motivating NL-level analysis.
- The extraction subsystem (evidence-span-guarded) is precisely the tool
  for populating both sides; the human-review CLI handles triage.

### Landmines and pre-emptions

- **"Why not Sail/formal tools?"** — stay strictly on the NL side: claim
  *screening/pattern detection*, never proof (same discipline as the q14
  rule in CLAUDE.md).
- **"CVA6 already documents deviations."** — the point is automated
  detection from prose without human-encoded exception lists; the WLRL case
  validates exactly that.
- **Version-mismatch findings can look trivial** — report them as a
  separate, clearly labelled finding class.
- **n=64 caveat:** the SpecGuard dataset is a subset; frame as
  proof-of-concept on the subset or ingest the full readthedocs spec.

**Effort:** ~3–6 weeks (ISA-side entity extraction is the bulk).
**Target:** the flagship experiment for the dissertation's unique niche;
strong Paper #4 (Sensors/Electronics) or standalone candidate.

---

## Strategic option (supervisor conversation, not unilateral)

Merge novelties #1 and #2 into one sharper thesis: **"the qualification
boundary is a first-class architectural element"** — agent roles defined by
automation level and qualifiability, BYOM as the mechanism keeping
unqualifiable components swappable, non-interference (Direction 2) as the
property making the boundary real. One sharp claim beats two diluted ones;
HMAS-as-standalone-novelty will age badly against the fast-moving agents
literature. Raise at the rescheduled supervisor meeting.

## Priority ordering (value per effort)

1. **Direction 3** (drift guard) — days; immediately publishable; feeds
   `/sg-refine` now. *Blocked only on the AirReq check.*
2. **Direction 1** (codification method) — the dissertation's academic
   spine; classification work, no new infrastructure.
3. **Direction 2** (non-interference + GSN) — defense-winning; mostly
   formalization of what exists.
4. **Direction 4** (CVA6 vs ISA) — flagship experiment if time allows;
   largest effort, highest demonstrative payoff.

## Citation backbone (verify all before manuscript use)

**Direction 1:** RACK (SAFECOMP-W 2023, doi:10.1007/978-3-031-40953-0_13;
DASC 2023/2024); DesCert (arXiv:2203.15178); Métayer & Paz (IEEE 2019);
Holloway NASA/TM-2014-218282; Cartile et al. (Aerospace 2025 12(8):724,
2026 13(5):460); OMG SACM v2.2; OntoGSN (arXiv:2506.11023); ISWC 2023
(doi:10.1007/978-3-031-47243-5_19); EMERALD (arXiv:2502.07330).

**Direction 2:** Liu et al. DASC 2025 (Loonwerks); Goguen & Meseguer 1982;
Hawkins et al. AMLAS (arXiv:2102.01564); Habli et al. BIG Argument
(arXiv:2503.11705); Bueno Momčilović et al. (arXiv:2410.05304); Nesti et
al. (arXiv:2509.21014); Bhattarai & Vu (arXiv:2602.09947); EASA AI Concept
Paper Issue 2 (2023); FAA AI Safety Assurance Roadmap v1 (2024); Fu et al.
TQL-5 COTS (J.Phys.Conf.Ser. 2882, 2024).

**Direction 3:** Veizaga, Shin & Briand (IEEE TSE 50(4), 2024); Dieste et
al. (REFSQ 2026, arXiv:2601.16699); Jia et al. SpecFix (arXiv:2505.07270);
Post, Fuhr et al. (NLP4RE, CEUR-2857, 2021); SummaC (Laban et al. 2022);
QAFactEval (Fabbri et al. 2022); SemEval-2024 Task 2 (arXiv:2404.04963);
InfoLossQA (ACL 2024); IEEE 29148:2018 / INCOSE GtWR (modal hierarchy);
AirReq (IEEE REW 2025) — **stance unverified, must check**.

**Direction 4:** RISCOF docs + riscv-arch-test; Sail RISC-V model; Reid
(RISC-V spec analyses); Çevikol & Aydemir (NLP4RE/REFSQ 2019, CEUR-2376);
Gärtner & Göhlich ALICE (Autom. Softw. Eng. 2024); Gärtner taxonomy (Appl.
Sci. 2022); RFC-vs-TCP/IP gaps (arXiv:2510.24408); SPECA
(arXiv:2602.07513); Masoudifard et al. (arXiv:2412.08593); transfer-learning
conflict pairs (arXiv:2301.03709).
