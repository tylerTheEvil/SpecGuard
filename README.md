# SpecGuard Prototype

Research prototype for the dissertation: *"Models and methods for AI-agentic
support of requirements engineering in the software lifecycle and FPGA
components of critical UAVs"*.

**Author:** Anton Stryapunin, KhAI, gr. F7-503-1
**Supervisor:** Prof. Yevhen Brezhnyev

---

## Quick start

```bash
# From the project root
python notebooks/experiment_seeded_faults.py
```

Or open the demo notebook:

```bash
jupyter notebook notebooks/01_specguard_demo.ipynb
```

---

## Project structure

```
specguard/
├── data/
│   └── cva6_requirements.py        # 64 industrial requirements from CVA6 spec
├── specguard/
│   ├── __init__.py
│   ├── smell_detector.py           # Rule-based smell detection (ISO/IEEE 29148)
│   ├── quality_scorer.py           # Quantitative quality scoring
│   └── pipeline.py                 # Pipeline orchestrator
├── notebooks/
│   ├── 01_specguard_demo.ipynb     # Walkthrough demo for supervisor
│   └── experiment_seeded_faults.py # Validation experiment
└── results/
    └── experiment_results.json     # Latest experiment output
```

---

## Methodology references

1. **Vogelsang & Korn (ICSE-NIER 2025)** — Requirements smell catalog and
   their impact on LLM-based traceability tasks.
2. **Veizaga et al. (IEEE TSE 2023)** — *Paska + Rimay CNL*: 89% precision
   and recall on industrial smell detection in 13 financial systems.
3. **Zakeri-Nasrabadi et al. (Neural Computing & Applications 2024)** —
   Mathematical model for quantitative testability scoring on 1000 industrial
   requirements.
4. **AirReq (IEEE REW 2025)** — Direct competitor / baseline: requirements
   smell detection for commercial aircraft systems (12 smell types, LLM + RAG).

---

## Dataset

**CVA6 Requirements Specification, Revision 1.0.1**

- Industrial-grade open-source RISC-V CPU specification
- Curator: Jerome Quevremont (Thales)
- Maintainer: OpenHW Group
- License: Apache-2.0 WITH SHL-2.1
- Source: https://docs.openhwgroup.org/projects/cva6-user-manual/02_cva6_requirements/cva6_requirements_specification.html

**Statistics:** 64 requirements across 9 categories (ISA, Privileges, Cache,
Performance, etc.). 12 requirements are tagged as safety-critical context.

---

## Latest results

**Pipeline run on 64 CVA6 requirements:**

| Metric | Value |
|--------|-------|
| Average overall quality | 0.888 |
| Gate PASS | 61 (95.3%) |
| Gate WARN | 1 |
| Gate FAIL | 2 (3.1%) |
| Smells detected | 9 |
| Smells per requirement | 0.14 |

**Validation on seeded faults (50 controlled mutations):**

| Fault type | Recall |
|------------|--------|
| Ambiguity | 100% |
| Vagueness | 100% |
| Optionality | 100% |
| Placeholder | 100% |
| Comparative | 100% |
| **Overall** | **100%** |

**False-positive baseline on clean dataset:** 12.5% (8 of 64 requirements
flagged with at least one smell — these include known-incomplete TBD entries).

---

## Comparison with original prototype

The original `ai_hdl_pipeline_demo.ipynb` used a single LLM prompt to evaluate
quality. SpecGuard uses an explicit, rule-based smell catalog with a
quantitative scoring model. Differences:

| Aspect | Original prototype | SpecGuard |
|--------|-------------------|-----------|
| Quality criteria | Implicit (LLM judgment) | Explicit catalog (ISO/IEEE 29148) |
| Output | Free-form text | Structured scores in [0,1] |
| Determinism | No | Yes |
| Auditable rules | No | Yes |
| Baseline metrics | None | Recall, FPR |
| DO-330 qualifiable | No (black box LLM) | In principle yes |

This is a deliberate design choice. The graph layer (next phase) will add
LLM-based reasoning on top of the deterministic smell foundation, so
auditable results are preserved.

---

## Next steps (post-demo)

1. **Graph layer**: Neo4j knowledge graph + Cypher queries for inter-requirement
   consistency.
2. **Regulatory codification**: DO-178C / DO-254 objectives as reusable graph
   schemas (the second scientific novelty of the dissertation).
3. **LLM augmentation**: combine deterministic smell detection with LLM
   reasoning for context-dependent issues (subjective phrasing, implicit
   contradictions).
4. **Cross-dataset validation**: extend to FVEval, VERT, and possibly
   industrial datasets through NVP "Radiy" collaboration.
