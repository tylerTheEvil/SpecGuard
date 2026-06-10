"""Quality Agent — wraps Layer 1 (deterministic detection + scoring + gate).

This agent is the HMAS embodiment of the *two-layer Quality Agent pattern*
(dissertation novelty #2): a deterministic detector (Layer 1, DO-330
qualifiable) optionally accompanied by an LLM analyst (Layer 2, augmentative).

Determinism invariant (load-bearing)
------------------------------------
The gate decisions and quality scores are produced by
``specguard.core.assess_dataset`` **before** any model is consulted, and the
``AgentReport.payload`` is fully populated from that deterministic result. The
optional BYOM provider is then asked, *separately*, for a plain-language
explanation that is stored only in ``AgentReport.llm_annotation``. No payload
field is read back from or conditioned on the model output. Therefore the gate
results are byte-for-byte identical whether or not a provider is attached — a
property asserted directly in ``tests/test_hmas.py``. This structural ordering
(compute, then annotate) is how the augmentative-not-authoritative claim is
made true in code rather than merely documented.
"""

from __future__ import annotations

from specguard.core import aggregate_metrics, assess_dataset

from .base import Agent, AgentReport, AgentRequest


class QualityAgent(Agent):
    """Wraps the deterministic Layer 1 pipeline; optional LLM analyst note."""

    role = "Quality Agent (Layer 1 deterministic gate + optional LLM analyst)"

    def run(self, request: AgentRequest) -> AgentReport:
        # --- Deterministic stage: detection -> scoring -> gate. ---
        # Computed unconditionally and first; this is the qualifiable result.
        results = assess_dataset(request.requirements)
        metrics = aggregate_metrics(results)

        per_requirement = [
            {
                "requirement_id": r.requirement_id,
                "gate_decision": r.gate_decision,
                "overall": round(r.quality_scores.overall, 3),
                "completeness": round(r.quality_scores.completeness, 3),
                "consistency": round(r.quality_scores.consistency, 3),
                "verifiability": round(r.quality_scores.verifiability, 3),
                "smell_count": r.smell_report.smell_count,
            }
            for r in results
        ]

        payload = {
            "aggregate": metrics,
            "per_requirement": per_requirement,
        }

        # --- Augmentative stage: LLM analyst note (optional, never feeds back). ---
        annotation: str | None = None
        used_provider: str | None = None
        if self.provider is not None:
            annotation = self._explain(metrics, per_requirement)
            used_provider = self.provider_name

        return AgentReport(
            agent_name=self.name,
            role=self.role,
            payload=payload,
            llm_annotation=annotation,
            used_provider=used_provider,
        )

    def _explain(self, metrics: dict, per_requirement: list[dict]) -> str:
        """Ask the BYOM provider for a plain-language summary of the findings.

        The prompt is built *from the already-finalised deterministic result*.
        The returned text is purely explanatory; it is never parsed back into
        a gate decision or score.
        """
        assert self.provider is not None  # guarded by the caller
        failing = [r["requirement_id"] for r in per_requirement
                   if r["gate_decision"] == "FAIL"]
        warning = [r["requirement_id"] for r in per_requirement
                   if r["gate_decision"] == "WARN"]
        prompt = (
            "The deterministic SpecGuard gate produced these results "
            "(already final — do not change them):\n"
            f"- requirements analysed: {metrics.get('total_requirements')}\n"
            f"- PASS/WARN/FAIL: {metrics.get('gate_pass')}/"
            f"{metrics.get('gate_warn')}/{metrics.get('gate_fail')}\n"
            f"- average overall score: {metrics.get('avg_overall')}\n"
            f"- FAIL ids: {failing}\n"
            f"- WARN ids: {warning}\n\n"
            "Write one short paragraph explaining these findings to a "
            "requirements engineer."
        )
        system = (
            "You are an augmentative analyst. You explain deterministic "
            "results in plain language. You never override or recompute them."
        )
        return self.provider.complete(prompt, system=system)
