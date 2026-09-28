"""spec-kit-specguard — deterministic requirement-quality gate for GitHub Spec Kit.

Layer 1 of the SpecGuard two-layer Quality Agent pattern, packaged as a Spec
Kit extension: rule-based smell detection (vendored SpecGuard core, Femmer
2017 lexicon methodology; scoring adapted from Zakeri-Nasrabadi 2024), a
Spec Kit register profile, structural checks codified from Spec Kit's own
specification-quality checklist, and spec<->tasks traceability checks.

Stdlib-only and Python >= 3.9: Spec Kit may run this with the user's project
interpreter, so no third-party imports are allowed anywhere in this package.
No model is involved in any verdict.
"""

__version__ = "0.1.0"
