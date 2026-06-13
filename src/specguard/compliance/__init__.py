"""SpecGuard Compliance Module — Codified Regulatory Objectives.

Implements the third scientific novelty of the dissertation:
codification of DO-178C / DO-254 regulatory objectives as executable
graph constraints (Cypher patterns).

This module contains a *representative subset* of objectives — proof of
concept demonstrating the methodology. Full codification of all DO-178C
(~71 obj) and DO-254 (~50 obj) objectives is identified as a separate
research direction comparable in scope to a normative-formalization PhD
thesis (cf. Yadamsuren et al. 2025 for IRC formalization in Prolog).

Architecture:
    Standard (DO-178C, DO-254)
        └─ contains ─→ Objective (id, table, applicable_dal, cypher_query)
                         └─ violation_template

Usage:
    from specguard.compliance import run_compliance_check
    from specguard.compliance.do178c import DO_178C_OBJECTIVES
    from specguard.compliance.do254 import DO_254_OBJECTIVES

    report = run_compliance_check(graph, DO_178C_OBJECTIVES + DO_254_OBJECTIVES)
"""

from .constraint_engine import (
    ComplianceConstraint,
    ComplianceReport,
    ComplianceViolation,
    run_compliance_check,
)
from .cross_domain import CROSS_DOMAIN_OBJECTIVES
from .do178c import DO_178C_OBJECTIVES
from .do254 import DO_254_OBJECTIVES

__all__ = [
    "ComplianceConstraint",
    "ComplianceReport",
    "ComplianceViolation",
    "run_compliance_check",
    "DO_178C_OBJECTIVES",
    "DO_254_OBJECTIVES",
    "CROSS_DOMAIN_OBJECTIVES",
]
