"""Requirements Smell Detector.

Implementation references the characteristics of well-formed requirements
defined in ISO/IEC/IEEE 29148:2018, sections 5.2.5 (individual requirements),
5.2.6 (set characteristics), and 5.2.7 (language criteria):
- Unambiguous, consistent, complete, verifiable
- Modal verb interpretation (shall/should/will/may)
- Avoidance of ambiguous and vague language

The 'requirement smell' concept and lexicon-based detection methodology
were introduced by:
- Femmer et al. (2017). "Rapid Quality Assurance with Requirements Smells".
  Journal of Systems and Software. — Foundational paper introducing
  smells as adaptation of code smells (Fowler 1999) to requirements.

Multi-dimensional quality scoring adapted from:
- Zakeri-Nasrabadi et al. (2024). "Natural language requirements testability
  measurement based on requirement smells". Neural Computing and Applications.

Research motivation:
- Vogelsang & Korn (2025) ICSE-NIER demonstrate empirical impact of
  requirements quality on downstream LLM-based tools.

This module implements rule-based detection (regex + lexicons) for fast,
reproducible, deterministic results suitable for DO-330 tool qualification
considerations. LLM-based augmentation (suggestions, explanations) is
provided in a separate module.

Future work:
- Recommendation engine inspired by Veizaga et al. (2023) IEEE TSE
  "Automated Smell Detection and Recommendation in NL Requirements".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class SmellType(str, Enum):  # noqa: UP042 — deliberate (str, Enum); StrEnum changes str() semantics
    """Catalog of requirement smells from ISO/IEEE 29148."""

    AMBIGUITY = "ambiguity"
    """Subjective or interpretation-dependent words (e.g., 'fast', 'easy')."""

    VAGUENESS = "vagueness"
    """Imprecise quantifiers (e.g., 'some', 'several', 'many')."""

    SUBJECTIVITY = "subjectivity"
    """Subjective phrases (e.g., 'user-friendly', 'as appropriate')."""

    OPTIONALITY = "optionality"
    """Optional language without firm commitment (excessive 'should', 'may')."""

    WEAKNESS = "weakness"
    """Weak phrases that bypass commitment (e.g., 'if possible', 'as needed')."""

    NON_VERIFIABLE = "non_verifiable"
    """Statements that cannot be objectively verified."""

    IMPLICIT_REFERENCE = "implicit_reference"
    """References to undefined entities (e.g., 'the system', 'the device')."""

    NEGATIVE_STATEMENT = "negative_statement"
    """Statements expressed negatively, harder to verify."""

    COMPARATIVE = "comparative"
    """Comparison without baseline (e.g., 'faster', 'better')."""

    PLACEHOLDER = "placeholder"
    """Explicit TBD / TODO markers — known incomplete content."""

    MISSING_UNIT = "missing_unit"
    """Numeric values without measurement unit."""


@dataclass
class SmellHit:
    """A single smell detection result."""

    smell_type: SmellType
    trigger: str
    """The word or phrase that triggered the detection."""

    position: int
    """Character offset within the requirement text."""

    severity: str
    """Severity: 'low', 'medium', 'high'."""

    explanation: str
    """Human-readable explanation of why this is problematic."""


@dataclass
class SmellReport:
    """Complete smell-detection report for a single requirement."""

    requirement_id: str
    requirement_text: str
    hits: list[SmellHit] = field(default_factory=list)

    @property
    def smell_count(self) -> int:
        return len(self.hits)

    @property
    def smell_types_found(self) -> set[SmellType]:
        return {hit.smell_type for hit in self.hits}

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = {"low": 0, "medium": 0, "high": 0}
        for hit in self.hits:
            counts[hit.severity] += 1
        return counts


# ============================================================================
# Smell lexicons — based on Femmer et al. 2017 and subsequent extensions
# ============================================================================

# Ambiguity: subjective adjectives and adverbs
AMBIGUITY_TERMS = {
    "fast", "slow", "quick", "quickly", "easy", "easily", "user-friendly",
    "appropriate", "appropriately", "sufficient", "sufficiently", "adequate",
    "adequately", "reasonable", "reasonably", "robust", "efficient", "efficiently",
    "secure", "secured", "safe", "safely", "reliable", "reliably", "flexible",
    "flexibly", "modern", "intuitive", "smooth", "seamless", "clean", "powerful",
    "simple", "simply", "complex", "minimal", "minimally", "optimal", "optimally",
    "scalable", "maintainable", "transparent",
}

# Vagueness: imprecise quantifiers
VAGUENESS_TERMS = {
    "some", "any", "many", "several", "few", "various", "different", "lots of",
    "a lot of", "plenty of", "numerous", "etc", "and so on", "and so forth",
    "approximately", "roughly", "around", "nearly", "almost", "typically",
    "usually", "often", "sometimes",
}

# Optionality: conditional skip phrases that allow the implementer to bypass the requirement.
# "as X" judgment phrases have been moved to SUBJECTIVITY_TERMS to avoid double-flagging.
OPTIONALITY_TERMS = {
    "if possible",
    "if needed",
    "if applicable",
    "if necessary",
    "if practical",
    "if feasible",
    "if reasonable",
    "where possible",
    "where applicable",
    "where required",
}

# Subjectivity: multi-word judgment phrases without an objective acceptance criterion.
# Distinct from AMBIGUITY (single adjectives) and OPTIONALITY (conditional skip phrases).
SUBJECTIVITY_TERMS = {
    "as appropriate",
    "where appropriate",
    "as needed",
    "as required",
    "as necessary",
    "as expected",
    "as desired",
    "common sense",
    "industry standard",
    "industry best practice",
    "best practice",
    "best practices",
    "state of the art",
    "state-of-the-art",
    "good performance",
    "acceptable performance",
    "reasonable performance",
    "high quality",
    "good quality",
}

# Weakness: weak modals and softening constructions that undermine normative force.
# Plain "should" and "may" are intentionally excluded — they carry formal RFC 2119 /
# ISO 29148 semantics (recommended and permitted, respectively) and flagging them
# would produce massive false positives on well-formed specifications.
WEAKNESS_TERMS = {
    "might",
    "could",
    "may want to",
    "may need to",
    "may consider",
    "is encouraged to",
    "are encouraged to",
    "is recommended to",
    "are recommended to",
}

# Non-verifiable action verbs: vague when used in normative context.
# "ensure" and "maintain" are intentionally excluded — they appear in many
# well-formed requirements with measurable criteria and produce too many false positives.
NON_VERIFIABLE_VERBS = {
    # "support" intentionally excluded: in ISA/hardware specs "shall support
    # [extension] version X" is a verifiable bounded claim. Including it
    # produces ~22 false positives on the CVA6 corpus with 0 true positives.
    "handle",
    "manage",
    "process",
    "deal with",
    "accommodate",
    "facilitate",
    "promote",
}

# Negative statement patterns
NEGATIVE_PATTERN = re.compile(
    r"\b(shall|must|will|should)\s+not\b",
    re.IGNORECASE,
)

DOUBLE_NEGATIVE_PATTERN = re.compile(
    r"\b(shall|must|will|should)\s+not\s+"
    r"(?:\w+\s+){0,3}"
    r"(fail|prevent|stop|deny|reject|refuse|block)\s+to\b",
    re.IGNORECASE,
)

# Implicit references — generic entity references without antecedent
IMPLICIT_REFERENCE_TERMS = {
    "the system", "the device", "the module", "the component", "the application",
    "the tool", "the platform", "the user", "this", "that", "it",
}

# Comparative without baseline
COMPARATIVE_PATTERN = re.compile(
    r"\b(faster|slower|better|worse|higher|lower|larger|smaller|"
    r"more efficient|less efficient|more reliable|less reliable|"
    r"more robust|less robust|more secure|less secure)\b",
    re.IGNORECASE,
)

# Numeric value followed by no unit (heuristic, false positives possible)
NUMERIC_NO_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s+(?!"
    # known units (extend as needed)
    r"(?:bit|bits|byte|bytes|kbyte|kbytes|mbyte|mbytes|gbyte|gbytes|"
    r"kb|mb|gb|kib|mib|gib|"
    r"hz|khz|mhz|ghz|"
    r"ns|us|ms|s|sec|seconds?|min|minutes?|hours?|"
    r"way|ways|cycle|cycles|"
    r"v|volt|volts|a|amp|amps|w|watt|watts|"
    r"deg|degree|degrees|c|f|"
    r"kg|gram|grams|m|meter|meters|km|"
    r"%|percent|"
    r"mhz/mhz|coremark|"
    r"of|or|and|to|from|in|on|with|"
    r"\d|\.|,|\)|;|:)\b)",
    re.IGNORECASE,
)

# Placeholder markers
PLACEHOLDER_PATTERN = re.compile(r"\b(TBD|TODO|FIXME|XXX|TBC)\b")


def _find_terms(text: str, terms: set[str]) -> list[tuple[str, int]]:
    """Find all occurrences of terms in text, case-insensitive."""
    found = []
    text_lower = text.lower()
    for term in terms:
        pattern = re.compile(r"\b" + re.escape(term.lower()) + r"\b")
        for match in pattern.finditer(text_lower):
            found.append((term, match.start()))
    return found


def detect_ambiguity(text: str) -> list[SmellHit]:
    """Detect ambiguous subjective adjectives and adverbs."""
    hits = []
    for term, pos in _find_terms(text, AMBIGUITY_TERMS):
        hits.append(
            SmellHit(
                smell_type=SmellType.AMBIGUITY,
                trigger=term,
                position=pos,
                severity="medium",
                explanation=(
                    f"The word '{term}' is subjective and open to interpretation. "
                    "Replace with measurable criteria where possible."
                ),
            )
        )
    return hits


def detect_vagueness(text: str) -> list[SmellHit]:
    """Detect imprecise quantifiers."""
    hits = []
    for term, pos in _find_terms(text, VAGUENESS_TERMS):
        # 'some' has high severity in safety contexts; default medium otherwise
        severity = "high" if term in {"some", "many", "etc"} else "medium"
        hits.append(
            SmellHit(
                smell_type=SmellType.VAGUENESS,
                trigger=term,
                position=pos,
                severity=severity,
                explanation=(
                    f"'{term}' is an imprecise quantifier. Specify exact "
                    "quantities or ranges."
                ),
            )
        )
    return hits


def detect_optionality(text: str) -> list[SmellHit]:
    """Detect weak optional phrasing.

    Note: 'should' alone is intentionally NOT flagged here, because in the
    industrial RFC2119 / ISO style 'should' has formal recommended-strength
    meaning. Only escape-hatch optional phrases are flagged.
    """
    hits = []
    text_lower = text.lower()
    for phrase in OPTIONALITY_TERMS:
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b")
        for match in pattern.finditer(text_lower):
            hits.append(
                SmellHit(
                    smell_type=SmellType.OPTIONALITY,
                    trigger=phrase,
                    position=match.start(),
                    severity="high",
                    explanation=(
                        f"The phrase '{phrase}' allows the implementer to "
                        "skip the requirement. Specify the exact conditions "
                        "under which this requirement applies."
                    ),
                )
            )
    return hits


def detect_subjectivity(text: str) -> list[SmellHit]:
    """Detect multi-word subjective judgment phrases without objective criterion.

    Distinct from AMBIGUITY (single subjective adjectives) and OPTIONALITY
    (conditional skip phrases). Targets expressions like 'as appropriate' or
    'industry best practice' that defer the acceptance criterion to the reader's
    judgment rather than specifying a measurable standard.
    """
    hits = []
    for term, pos in _find_terms(text, SUBJECTIVITY_TERMS):
        hits.append(
            SmellHit(
                smell_type=SmellType.SUBJECTIVITY,
                trigger=term,
                position=pos,
                severity="medium",
                explanation=(
                    f"The phrase '{term}' expresses subjective judgment without "
                    "an objective acceptance criterion. Replace with measurable "
                    "criteria where possible."
                ),
            )
        )
    return hits


def detect_weakness(text: str) -> list[SmellHit]:
    """Detect weak modal verbs and softening constructions.

    Flags 'might', 'could', and multi-word softeners ('may want to', etc.)
    that undermine the normative force of a requirement. Plain 'should' and
    'may' are intentionally excluded — they carry formal RFC 2119 / ISO 29148
    semantics and flagging them produces false positives on well-formed specs.
    """
    hits = []
    for term, pos in _find_terms(text, WEAKNESS_TERMS):
        hits.append(
            SmellHit(
                smell_type=SmellType.WEAKNESS,
                trigger=term,
                position=pos,
                severity="high",
                explanation=(
                    f"The expression '{term}' weakens the requirement's normative "
                    "force. Use 'shall' for mandatory behaviour or specify exact "
                    "conditions."
                ),
            )
        )
    return hits


def detect_non_verifiable(text: str) -> list[SmellHit]:
    """Detect vague action verbs in normative context (heuristic, low severity).

    Only flags the verb when preceded within 25 characters by a modal verb
    (shall / should / will / must), restricting detection to the normative-action
    context where the verb's vagueness matters most.

    'ensure' and 'maintain' are intentionally excluded — they appear frequently
    in well-formed requirements with measurable criteria.
    """
    hits = []
    text_lower = text.lower()
    for verb in NON_VERIFIABLE_VERBS:
        pattern = re.compile(r"\b" + re.escape(verb) + r"\b")
        for match in pattern.finditer(text_lower):
            preceding = text_lower[max(0, match.start() - 25) : match.start()]
            if not re.search(r"\b(shall|should|will|must)\b", preceding):
                continue
            hits.append(
                SmellHit(
                    smell_type=SmellType.NON_VERIFIABLE,
                    trigger=verb,
                    position=match.start(),
                    severity="low",
                    explanation=(
                        f"The verb '{verb}' may lack a measurable acceptance "
                        "criterion. Verify that the requirement specifies "
                        "concrete success conditions."
                    ),
                )
            )
    return hits


def detect_negative_statement(text: str) -> list[SmellHit]:
    """Detect negative formulations and double negations.

    ISO 29148 and Femmer 2017 note that positive formulations are easier to
    verify than negative ones. Double negations (high severity) are checked
    first; simple negations (low severity) that overlap a double-negation
    match are suppressed to avoid duplicate hits.
    """
    hits = []
    flagged_ranges: list[tuple[int, int]] = []

    for match in DOUBLE_NEGATIVE_PATTERN.finditer(text):
        hits.append(
            SmellHit(
                smell_type=SmellType.NEGATIVE_STATEMENT,
                trigger=match.group(0),
                position=match.start(),
                severity="high",
                explanation=(
                    f"'{match.group(0)}' contains a double negation, which is "
                    "hard to interpret and verify. Rephrase positively."
                ),
            )
        )
        flagged_ranges.append((match.start(), match.end()))

    for match in NEGATIVE_PATTERN.finditer(text):
        if any(start <= match.start() < end for start, end in flagged_ranges):
            continue
        hits.append(
            SmellHit(
                smell_type=SmellType.NEGATIVE_STATEMENT,
                trigger=match.group(0),
                position=match.start(),
                severity="low",
                explanation=(
                    f"'{match.group(0)}' is a negative formulation. Positive "
                    "formulations are usually easier to verify. Consider "
                    "rephrasing if practical."
                ),
            )
        )
    return hits


def detect_comparatives(text: str) -> list[SmellHit]:
    """Detect comparatives without explicit baseline."""
    hits = []
    for match in COMPARATIVE_PATTERN.finditer(text):
        # Check if there's a comparison anchor like "than X" within next 20 chars
        following = text[match.end() : match.end() + 30].lower()
        if " than " in following or "compared to" in following or "relative to" in following:
            continue  # has baseline
        hits.append(
            SmellHit(
                smell_type=SmellType.COMPARATIVE,
                trigger=match.group(0),
                position=match.start(),
                severity="medium",
                explanation=(
                    f"'{match.group(0)}' is a comparative without an explicit "
                    "baseline. Specify what it is being compared against."
                ),
            )
        )
    return hits


def detect_placeholders(text: str) -> list[SmellHit]:
    """Detect TBD / TODO markers — known incomplete content."""
    hits = []
    for match in PLACEHOLDER_PATTERN.finditer(text):
        hits.append(
            SmellHit(
                smell_type=SmellType.PLACEHOLDER,
                trigger=match.group(0),
                position=match.start(),
                severity="high",
                explanation=(
                    f"The marker '{match.group(0)}' indicates incomplete "
                    "content. The requirement must be filled in before it can "
                    "be considered finalized."
                ),
            )
        )
    return hits


def detect_implicit_references(text: str) -> list[SmellHit]:
    """Detect generic entity references without explicit antecedent.

    Heuristic: flag generic references near the start of the requirement.
    The first 'the system' is usually fine; subsequent generic references
    are more suspicious. This is a conservative heuristic — false positives
    are expected and acceptable for first-line screening.
    """
    hits = []
    text_lower = text.lower()
    # Only flag truly ambiguous references — pronouns at unusual positions
    # 'this' and 'that' as standalone words are most suspicious
    for term in ["this", "that", "it"]:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b")
        # We only flag if the pronoun appears in subject position (start) or
        # immediately after a comma — heuristic for ambiguity
        for match in pattern.finditer(text_lower):
            # Check context: is there a clear noun antecedent right before?
            preceding = text_lower[max(0, match.start() - 20) : match.start()].strip()
            if preceding.endswith(",") or preceding == "" or match.start() < 10:
                hits.append(
                    SmellHit(
                        smell_type=SmellType.IMPLICIT_REFERENCE,
                        trigger=term,
                        position=match.start(),
                        severity="low",
                        explanation=(
                            f"The pronoun '{term}' may refer to multiple "
                            "entities. Use explicit nouns to avoid ambiguity."
                        ),
                    )
                )
    return hits


def detect_missing_unit(text: str) -> list[SmellHit]:
    """Detect numeric values that appear without measurement units.

    Heuristic — false positives expected. Tuned to be conservative.
    """
    hits = []
    for match in NUMERIC_NO_UNIT_PATTERN.finditer(text):
        # Skip very short numbers (likely identifiers like version numbers)
        if "." in match.group(1) and len(match.group(1)) <= 4:
            continue
        # Skip common false positives like "version 2.1"
        preceding = text[max(0, match.start() - 15) : match.start()].lower()
        if any(
            kw in preceding
            for kw in ["version", "chapter", "section", "rev", "v.", "axi", "sv"]
        ):
            continue
        hits.append(
            SmellHit(
                smell_type=SmellType.MISSING_UNIT,
                trigger=match.group(1),
                position=match.start(),
                severity="low",
                explanation=(
                    f"The numeric value '{match.group(1)}' may be missing a "
                    "measurement unit. Verify that the unit is clear from context."
                ),
            )
        )
    return hits


# Detector registry — order is preserved in reports
DETECTORS = [
    # Ambiguity category
    detect_ambiguity,
    detect_vagueness,
    detect_subjectivity,
    detect_implicit_references,
    detect_comparatives,
    # Verifiability category
    detect_optionality,
    detect_weakness,
    detect_non_verifiable,
    detect_negative_statement,
    # Structural category
    detect_placeholders,
    detect_missing_unit,
]


def analyze_requirement(req_id: str, text: str) -> SmellReport:
    """Run all smell detectors on a requirement and return a report."""
    report = SmellReport(requirement_id=req_id, requirement_text=text)
    for detector in DETECTORS:
        report.hits.extend(detector(text))
    # Sort hits by position for readability
    report.hits.sort(key=lambda h: h.position)
    return report


def analyze_dataset(requirements: list) -> list[SmellReport]:
    """Run smell analysis on a list of Requirement objects."""
    reports = []
    for req in requirements:
        report = analyze_requirement(req.req_id, req.text)
        reports.append(report)
    return reports
