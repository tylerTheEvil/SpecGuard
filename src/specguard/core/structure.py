"""Structural (segment-level) requirement smells — opt-in, stdlib-only.

The lexical detectors in ``smell_detector`` flag *words* (``fast``, ``some``,
``TBD``). This module flags *structure*: a requirement whose condition, actor,
modal verb or system response is missing, misplaced, or overloaded. It closes
the part of ISO/IEC/IEEE 29148 §5.2.5 that a lexicon cannot see — *singular*
(one function per requirement) and the internal side of *complete*.

Attribution (adopted, not contributed):

- Smell catalogue and the segment model (condition / actor / modal / system
  response) are adapted from Veizaga, Shin & Briand (2024), "Automated Smell
  Detection and Recommendation in Natural Language Requirements", IEEE TSE
  50(4):695-720, DOI 10.1109/TSE.2024.3361033 (tool: Paska; CNL: Rimay).
- Condition keywords follow EARS (Mavin et al., RE 2009) rather than Rimay:
  EARS is the de-facto template in aerospace, Rimay targets financial
  information systems.

What differs from Paska — engineering trade-offs, not novelty claims:

- **No parser.** Paska uses POS tagging, constituency parsing and Tregex.
  This module uses keyword segmentation and regular expressions only, so it
  stays inside the stdlib-only, deterministic core (DO-330 TQL-5
  qualifiability argument, see ``docs/architecture.md``). The price is
  recall: smells that need a POS tag (Paska's "incomplete condition" — a
  condition without actor or verb) are not implemented here; they belong in
  the optional ``[linguistic]`` extra if needed.
- **Conservative actor check.** Without a parser the actor is only judged
  missing when the text between the last condition and the modal verb is
  empty (e.g. ``"When X, shall Y."``). A comma-free ``"When X the FC shall Y"``
  is never flagged.
- **Stative participles are not passive voice.** ``"While the vehicle is
  armed"`` is an EARS state, not a missing actor. A small, profile-tunable
  exemption list (``STATIVE_PARTICIPLES``) and the rule "WHILE conditions are
  states" keep this from flooding avionics/PX4-style text.

Opt-in: nothing here runs unless the caller asks for it
(``analyze_structure`` directly, ``assess_requirement(..., structural=True)``
or ``specguard assess --structural``). The default Layer 1 gate, and every
number reported on CVA6 / seeded faults / the spec-kit corpus, is unchanged.
Severities are provisional and **uncalibrated**; calibrate on a held-out
corpus before reporting precision/recall.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .smell_detector import OPTIONALITY_TERMS, SmellHit, SmellReport


class StructuralSmellType(str, Enum):  # noqa: UP042 — same convention as SmellType
    """Segment-level smells, adapted from Veizaga et al. (2024), Table III."""

    NOT_A_REQUIREMENT = "not_a_requirement"
    """No normative modal verb and no condition: a statement, not a requirement."""

    INCOMPLETE_REQUIREMENT = "incomplete_requirement"
    """Condition(s) present, but no modal verb / system response follows."""

    INCOMPLETE_RESPONSE = "incomplete_response"
    """Modal verb present, but the actor before it or the action after it is empty."""

    INCORRECT_ORDER = "incorrect_order"
    """A condition clause follows the system response (EARS: condition first)."""

    COORDINATION_AMBIGUITY = "coordination_ambiguity"
    """Conditions joined with 'or' mixed with 'and', or several clauses joined by 'or'."""

    NON_ATOMIC = "non_atomic"
    """More than one system response in one requirement (ISO 29148 'singular')."""

    PASSIVE_VOICE = "passive_voice"
    """Passive construction in an event condition or the response: likely missing actor."""


# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------

# Normative modals that open a system response. 'can'/'could'/'might' are not
# normative (they are handled as weakness smells by smell_detector).
MODAL_PATTERN = re.compile(r"\b(shall|must|will|should|may)(\s+not)?\b", re.IGNORECASE)

# Keywords that open a leading condition clause (EARS + common variants).
LEADING_CONDITION_PATTERN = re.compile(
    r"^\s*(when|whenever|while|where|if|after|before|upon|once|during|unless|in\s+case\s+of|"
    r"in\s+case)\b",
    re.IGNORECASE,
)

# Keywords that, appearing *after* the modal, introduce a trailing condition.
# 'after'/'before'/'once' are excluded on purpose: after a modal they are
# usually temporal objects ("report within 1 s after detection").
TRAILING_CONDITION_PATTERN = re.compile(
    r"(?<![-\w\[])(when|whenever|if|while|unless|in\s+case\s+of|in\s+case)(?![-\w\]])",
    re.IGNORECASE,
)
# 'upon' is leading-only: after a modal it is usually a prepositional phrase
# inside the response ("invalidates the line upon request", CVA6 L1W-50).
# The identifier guards keep "[CV-X-IF]" (CVA6 XIF-10) from matching 'if'.

# Condition keywords counted when deciding how many condition clauses exist.
CONDITION_KEYWORD_PATTERN = re.compile(
    r"\b(when|whenever|while|where|if|after|before|upon|during|unless)\b",
    re.IGNORECASE,
)

# Base-form action verbs used to spot a second, modal-less response
# ("shall add X and allow Y"). Deliberately small; extend per domain profile.
# fmt: off
ACTION_VERBS = frozenset({
    "abort", "accept", "activate", "add", "allow", "arm", "block", "broadcast",
    "calculate", "clear", "close", "command", "compute", "deactivate",
    "deny", "disable", "disarm", "discard", "display", "enable", "engage",
    "enter", "execute", "exit", "generate", "hold", "ignore", "initiate",
    "land", "limit", "log", "monitor", "notify", "open", "publish", "raise",
    "record", "reject", "release", "remove", "report", "request", "reset",
    "restart", "resume", "retry", "return", "save", "send", "set", "signal",
    "start", "stop", "store", "switch", "terminate", "transition", "transmit",
    "trigger", "update", "validate", "warn", "write",
})

# Irregular past participles (regular ones are caught by the -ed suffix).
IRREGULAR_PARTICIPLES = frozenset({
    "begun", "bound", "broken", "brought", "built", "caught", "chosen", "done",
    "drawn", "driven", "fed", "found", "given", "held", "hidden", "kept",
    "known", "laid", "led", "left", "lost", "made", "meant", "met", "paid",
    "put", "read", "run", "said", "seen", "sent", "set", "shown", "shut",
    "sold", "split", "spent", "taken", "thrown", "told", "understood",
    "withdrawn", "written",
})

# Participles that describe a *state*, not an action with a hidden actor.
# Profile-tunable; the list is tuned for avionics / flight-stack wording.
STATIVE_PARTICIPLES = frozenset({
    "armed", "disarmed", "enabled", "disabled", "connected", "disconnected",
    "powered", "locked", "unlocked", "engaged", "disengaged", "selected",
    "required", "allowed", "permitted", "supported", "based", "located",
    "installed", "mounted", "equipped", "compliant", "aligned", "calibrated",
    "initialized", "initialised", "configured", "detected", "lost",
    "related", "unrelated", "limited", "bounded", "reserved", "dedicated",
})
# fmt: on

PASSIVE_PATTERN = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+(?:(?:not|\w+ly)\s+)?([a-z]+)\b",
    re.IGNORECASE,
)

_SEVERITY = {
    StructuralSmellType.NOT_A_REQUIREMENT: "medium",
    StructuralSmellType.INCOMPLETE_REQUIREMENT: "high",
    StructuralSmellType.INCOMPLETE_RESPONSE: "medium",
    StructuralSmellType.INCORRECT_ORDER: "low",
    StructuralSmellType.COORDINATION_AMBIGUITY: "medium",
    StructuralSmellType.NON_ATOMIC: "medium",
    StructuralSmellType.PASSIVE_VOICE: "low",
}


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


@dataclass
class RequirementStructure:
    """Keyword segmentation of one requirement (no parser, offsets into text).

    ``condition`` / ``actor`` / ``response`` are ``None`` when absent. ``actor``
    is ``""`` when the segmenter can *prove* it is empty (prefix ends with a
    comma or 'then'), and ``None`` when it cannot tell — callers must treat
    only ``""`` as a missing actor.
    """

    text: str
    condition: str | None = None
    condition_span: tuple[int, int] | None = None
    actor: str | None = None
    modal: str | None = None
    modal_span: tuple[int, int] | None = None
    response: str | None = None
    response_span: tuple[int, int] | None = None
    modal_count: int = 0
    modal_spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def has_condition(self) -> bool:
        return self.condition is not None

    @property
    def has_modal(self) -> bool:
        return self.modal is not None


def segment_requirement(text: str) -> RequirementStructure:
    """Split a requirement into condition / actor / modal / response by keywords.

    The first normative modal verb splits the text. A prefix that starts with
    an EARS condition keyword is the condition; if the prefix contains a comma
    (or 'then'), everything after the last such separator is the actor.
    """
    structure = RequirementStructure(text=text)
    modals = list(MODAL_PATTERN.finditer(text))
    structure.modal_count = len(modals)
    structure.modal_spans = [m.span() for m in modals]

    prefix_end = modals[0].start() if modals else len(text)
    prefix = text[:prefix_end]

    if modals:
        first = modals[0]
        structure.modal = first.group(0).lower()
        structure.modal_span = first.span()
        response = text[first.end() :]
        structure.response = response.strip()
        structure.response_span = (first.end(), len(text))

    if LEADING_CONDITION_PATTERN.match(prefix):
        separator = None
        for match in re.finditer(r",|\bthen\b", prefix, re.IGNORECASE):
            separator = match
        if separator is not None and modals:
            structure.condition = prefix[: separator.start()].strip()
            structure.condition_span = (0, separator.start())
            structure.actor = prefix[separator.end() :].strip(" ,")
        else:
            # Either no modal (whole text is the condition) or no separator
            # (actor is somewhere inside — undecidable without a parser).
            structure.condition = prefix.strip()
            structure.condition_span = (0, prefix_end)
            structure.actor = None
    elif modals:
        structure.actor = prefix.strip()

    return structure


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


SENTENCE_BREAK = re.compile(r"[.;]\s+(?=[A-Z\[])")


def _first_sentence_end(text: str, start: int, end: int) -> int:
    """End offset of the sentence that starts the [start, end) region.

    Later sentences without their own modal are notes/rationale ("The
    upper-bound is fixed but not specified here.", CVA6 L1W-10); a later
    sentence *with* a modal is already reported as NON_ATOMIC.
    """
    match = SENTENCE_BREAK.search(text, start, end)
    return match.start() if match else end


def _inside_parentheses(text: str, pos: int) -> bool:
    return text.count("(", 0, pos) > text.count(")", 0, pos)


def _hit(kind: StructuralSmellType, trigger: str, position: int, explanation: str) -> SmellHit:
    # SmellHit.smell_type is annotated as SmellType; StructuralSmellType is a
    # sibling str-Enum with the same serialisation contract (``.value``).
    return SmellHit(
        smell_type=kind,  # type: ignore[arg-type]
        trigger=trigger,
        position=position,
        severity=_SEVERITY[kind],
        explanation=explanation,
    )


def detect_missing_parts(s: RequirementStructure) -> list[SmellHit]:
    """NOT_A_REQUIREMENT, INCOMPLETE_REQUIREMENT, INCOMPLETE_RESPONSE."""
    text = s.text
    if not text.strip():
        return []
    if not s.has_modal:
        if s.has_condition:
            return [
                _hit(
                    StructuralSmellType.INCOMPLETE_REQUIREMENT,
                    text.strip()[:40],
                    0,
                    "The requirement states a condition but no normative system "
                    "response (no 'shall'/'must' clause): it is unclear what the "
                    "system is obliged to do. Add the response with a modal verb.",
                )
            ]
        return [
            _hit(
                StructuralSmellType.NOT_A_REQUIREMENT,
                text.strip()[:40],
                0,
                "No normative modal verb and no condition: this reads as a "
                "statement or note, not a requirement.",
            )
        ]

    hits: list[SmellHit] = []
    assert s.modal_span is not None
    if s.actor == "":
        hits.append(
            _hit(
                StructuralSmellType.INCOMPLETE_RESPONSE,
                s.modal or "",
                s.modal_span[0],
                "The system response has no actor: name the component that "
                f"'{s.modal}' applies to.",
            )
        )
    if not re.search(r"[A-Za-z]", s.response or ""):
        hits.append(
            _hit(
                StructuralSmellType.INCOMPLETE_RESPONSE,
                s.modal or "",
                s.modal_span[0],
                f"Nothing follows '{s.modal}': the system response has no action.",
            )
        )
    return hits


def detect_incorrect_order(s: RequirementStructure) -> list[SmellHit]:
    """A condition clause after the modal verb (EARS places conditions first)."""
    if not s.has_modal or s.response_span is None:
        return []
    start, end = s.response_span
    response = s.text[start : _first_sentence_end(s.text, start, end)]
    hits: list[SmellHit] = []
    optional = [p for p in OPTIONALITY_TERMS if p.startswith(("if ", "where "))]
    for match in TRAILING_CONDITION_PATTERN.finditer(response):
        word = match.group(1).lower()
        tail = response[match.start() :].lower()
        if any(tail.startswith(p) for p in optional):
            continue  # "if possible" — an optionality smell, not a condition
        if word == "while" and re.match(r"while\s+\w+ing\b", tail):
            continue  # manner clause ("while maintaining heading")
        if _inside_parentheses(s.text, start + match.start()):
            continue  # parenthetical qualifier ("... hypervisor if present)", FET-20)
        split = s.has_condition
        hits.append(
            _hit(
                StructuralSmellType.INCORRECT_ORDER,
                match.group(0),
                start + match.start(),
                (
                    "Conditions appear both before and after the system response; "
                    "readers cannot tell which applies to what. Move all conditions "
                    "in front (EARS: When/While/If ..., <actor> shall ...)."
                    if split
                    else "The condition follows the system response. Put it first "
                    "(EARS: When/While/If ..., <actor> shall ...) so the trigger "
                    "is read before the action."
                ),
            )
        )
        break  # one hit per requirement is enough to locate the problem
    return hits


def detect_coordination_ambiguity(s: RequirementStructure) -> list[SmellHit]:
    """'or' combined with 'and' (precedence unclear) or 'or' across clauses."""
    if s.condition is None or s.condition_span is None:
        return []
    cond = s.condition
    has_or = re.search(r"\bor\b", cond, re.IGNORECASE)
    if not has_or:
        return []
    has_and = re.search(r"\band\b", cond, re.IGNORECASE)
    n_clauses = len(CONDITION_KEYWORD_PATTERN.findall(cond))
    if has_and or n_clauses >= 2:
        return [
            _hit(
                StructuralSmellType.COORDINATION_AMBIGUITY,
                "or",
                s.condition_span[0] + has_or.start(),
                "The condition mixes 'or' with 'and' or joins several condition "
                "clauses with 'or'; operator precedence is open to interpretation. "
                "Split into separate requirements or state the grouping explicitly.",
            )
        ]
    return []


def detect_non_atomic(s: RequirementStructure) -> list[SmellHit]:
    """More than one system response (ISO 29148 'singular')."""
    if not s.has_modal:
        return []
    if s.modal_count > 1:
        second = s.modal_spans[1]
        return [
            _hit(
                StructuralSmellType.NON_ATOMIC,
                s.text[second[0] : second[1]],
                second[0],
                "The requirement contains more than one modal clause, i.e. more "
                "than one system response. Split it so each can be verified and "
                "traced on its own.",
            )
        ]
    assert s.response_span is not None
    start, _ = s.response_span
    response = s.text[start:]
    for match in re.finditer(r"\b(?:and|,\s*and|;\s*and)\s+(\w+)\b", response, re.IGNORECASE):
        if match.group(1).lower() in ACTION_VERBS:
            return [
                _hit(
                    StructuralSmellType.NON_ATOMIC,
                    match.group(0),
                    start + match.start(),
                    f"'{match.group(1)}' starts a second action in the same "
                    "system response. Split it so each action can be verified "
                    "and traced on its own.",
                )
            ]
    return []


def _is_passive(participle: str) -> bool:
    word = participle.lower()
    if word in STATIVE_PARTICIPLES:
        return False
    return word in IRREGULAR_PARTICIPLES or (word.endswith("ed") and len(word) > 4)


def detect_passive_voice(s: RequirementStructure) -> list[SmellHit]:
    """Passive voice in an event condition or the system response.

    WHILE/WHERE conditions describe states/features and are skipped; stative
    participles ("is armed") are exempt everywhere. In the response, a passive
    with an explicit 'by <agent>' is not flagged.
    """
    hits: list[SmellHit] = []
    regions: list[tuple[int, int]] = []
    if s.condition_span is not None and not re.match(
        r"^\s*(while|where)\b", s.condition or "", re.IGNORECASE
    ):
        regions.append(s.condition_span)
    if s.response_span is not None:
        r_start, r_end = s.response_span
        regions.append((r_start, _first_sentence_end(s.text, r_start, r_end)))
    for start, end in regions:
        segment = s.text[start:end]
        for match in PASSIVE_PATTERN.finditer(segment):
            participle = match.group(2)
            if not _is_passive(participle):
                continue
            clause = re.split(r"[.;]", segment[match.end() :], maxsplit=1)[0]
            if re.search(r"\bby\s+(?!means\b|using\b|default\b)", clause, re.IGNORECASE):
                continue  # agent is named
            hits.append(
                _hit(
                    StructuralSmellType.PASSIVE_VOICE,
                    match.group(0),
                    start + match.start(),
                    f"'{match.group(0)}' is passive: it hides who performs the "
                    "action. Name the actor (e.g. 'When <component> receives ...').",
                )
            )
            break  # one hit per region
    return hits


STRUCTURAL_DETECTORS = [
    detect_missing_parts,
    detect_incorrect_order,
    detect_coordination_ambiguity,
    detect_non_atomic,
    detect_passive_voice,
]


def detect_structural_smells(text: str) -> list[SmellHit]:
    """Run all structural detectors on one requirement text."""
    structure = segment_requirement(text)
    hits: list[SmellHit] = []
    for detector in STRUCTURAL_DETECTORS:
        hits.extend(detector(structure))
    hits.sort(key=lambda h: h.position)
    return hits


def analyze_structure(req_id: str, text: str) -> SmellReport:
    """Structural-only report, same shape as ``smell_detector.analyze_requirement``."""
    return SmellReport(
        requirement_id=req_id, requirement_text=text, hits=detect_structural_smells(text)
    )
