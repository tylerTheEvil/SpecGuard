"""SpecGuard — Multi-layered quality gate for requirements engineering."""

from specguard.core import (
    AssessmentResult,
    QualityScores,
    SmellHit,
    SmellReport,
    SmellType,
    aggregate_metrics,
    analyze_dataset,
    analyze_requirement,
    assess_dataset,
    assess_requirement,
    score_requirement,
)

__version__ = "0.1.0"

__all__ = [
    "AssessmentResult",
    "QualityScores",
    "SmellHit",
    "SmellReport",
    "SmellType",
    "aggregate_metrics",
    "analyze_dataset",
    "analyze_requirement",
    "assess_dataset",
    "assess_requirement",
    "score_requirement",
]
