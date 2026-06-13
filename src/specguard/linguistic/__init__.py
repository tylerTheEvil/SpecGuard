"""SpecGuard linguistic metrics — optional research extension.

Install the extra before importing:
    pip install -e '.[linguistic]'
    python -m spacy download en_core_web_sm
"""

from .metrics import LinguisticMetrics, compute_linguistic_metrics

__all__ = ["LinguisticMetrics", "compute_linguistic_metrics"]
