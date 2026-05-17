# SpecGuard Architecture Overview

> Canonical reference for the three scientific novelties of the dissertation.
> Full rationale is in the Notion literature review:
> https://www.notion.so/351c18673187810f998ed912dbe4c5ec

## Positioning

SpecGuard is an architectural framework for multi-layered quality gate in
requirements engineering for safety-critical software and FPGA systems
(DO-178C / DO-254 / DO-330 TQL-5). It is not a smell linter — the novelty is
the architectural composition, not the individual techniques.

## Three-layer gate

```
Layer 1 — Deterministic detection     src/specguard/core/
Layer 2 — Knowledge graph             src/specguard/graph/
Layer 3 — Compliance codification     src/specguard/compliance/
```

### Layer 1: Deterministic smell detection (DO-330 qualifiable)

- 11 smell types, methodology from Femmer et al. (2017) operationalizing ISO/IEEE 29148
- Rule-based only — no LLM in detection path (required for DO-330 qualifiability)
- Quality scoring adapted from Zakeri-Nasrabadi et al. (2024)
- Gate decisions: PASS / WARN / FAIL

### Layer 2: Knowledge graph (Neo4j / NetworkX)

- Property graph: Requirement → Component / Standard / Configuration / Smell nodes
- 107 nodes / 171 relationships on the CVA6 dataset
- Q14 (`q14_potential_conflicts`) is a topological screening filter, not conflict detection
- Full conflict detection (FSARC 7 types) is planned as Layer 2 Cypher queries

### Layer 3: Compliance codification (cross-domain)

- 15 representative objectives: 7 DO-178C + 5 DO-254 + 3 cross-domain
- Objectives expressed as Cypher graph queries (executable on real Neo4j)
- Cross-domain SW↔FPGA binding is the unique niche — no prior precedent in literature
- Full codification of ~71 DO-178C + ~50 DO-254 objectives is a separate research direction

## Hierarchical Multi-Agent System (HMAS) — planned

```
Coordinator Agent
├── Quality Agent        (Layer 1 + LLM analyst)
├── Formalization Agent  (Layer 2 graph queries)
└── Traceability Agent   (Layer 3 compliance + cross-domain)
```

Polyglot persistence: Neo4j (graph) + MongoDB (documents) + VectorDB (embeddings).
BYOM (Bring Your Own Model) interface — heterogeneous models per agent role.

## Optional linguistic metrics layer

```
src/specguard/linguistic/   (install: pip install -e '.[linguistic]')
```

Classical readability and syntactic complexity metrics that run in parallel
to the smell-based gate — they do not feed into PASS/WARN/FAIL decisions.

**Rationale:** These metrics are expected as a descriptive baseline by NLP4RE
reviewers (Zakeri-Nasrabadi 2024, Sonbol 2022, Kummler 2021). They are NOT
part of the dissertation's architectural novelty; they provide corroborating
evidence that the CVA6 dataset is representative technical text.

**Why separate from core:** the deterministic core must be stdlib-only for
DO-330 qualifiability considerations. `textstat` and `spacy` are third-party
libraries incompatible with that constraint. The `linguistic` subpackage is
therefore an optional extension that degrades gracefully to `None` when not
installed.

| Metric | Library | Reference |
|--------|---------|-----------|
| Flesch Reading Ease | textstat | Flesch (1948) |
| Flesch-Kincaid Grade | textstat | Kincaid et al. (1975) |
| Mean Dependency Length | spaCy | Barbosa et al. (2024) INCOSE |
| Max Dependency Length | spaCy | — |
| Token / sentence count | spaCy | standard |
| Lexical density | spaCy | standard |

Expected ranges on CVA6 (technical hardware requirements):
Flesch RE ≈ 25–50, FK Grade ≈ 12–16, MDL ≈ 3.0–5.0, Lexical density ≈ 0.50–0.70.

## Key design constraints

- Detection path must remain deterministic → LLMs only for analysis/explanation
- DO-330 TQL-5 positioning: development tool with human-in-the-loop, not airborne AI
- AirReq (IEEE REW 2025) is the direct comparison baseline
- Q14 / FSARC results must not be described as "conflict detection" — they are screening
