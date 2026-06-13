"""Unit tests for the pipeline orchestrator."""


from specguard import aggregate_metrics, assess_dataset, assess_requirement
from specguard.core.pipeline import AssessmentResult


class TestAssessRequirement:
    def test_returns_assessment_result(self):
        result = assess_requirement("T1", "The system shall respond within 100 ms.")
        assert isinstance(result, AssessmentResult)

    def test_gate_pass_for_clean_requirement(self):
        isa_req = (
            "The CVA6 processor shall implement the RV64GC ISA"
            " in compliance with [RVunpriv] v20191213."
        )
        result = assess_requirement("T2", isa_req)
        assert result.gate_decision == "PASS"

    def test_gate_warn_or_fail_for_smelly_requirement(self):
        result = assess_requirement("T3", "The system shall be fast.")
        assert result.gate_decision in ("WARN", "FAIL")

    def test_gate_fail_for_placeholder(self):
        result = assess_requirement("T4", "TBD: Performance target.")
        assert result.gate_decision == "FAIL"


class TestAssessDataset:
    def test_returns_list_of_results(self, cva6_requirements):
        results = assess_dataset(cva6_requirements)
        assert len(results) == len(cva6_requirements)
        assert all(isinstance(r, AssessmentResult) for r in results)

    def test_majority_pass(self, cva6_requirements):
        results = assess_dataset(cva6_requirements)
        pass_count = sum(1 for r in results if r.gate_decision == "PASS")
        assert pass_count / len(results) >= 0.90


class TestAggregateMetrics:
    def test_aggregate_keys(self, cva6_requirements):
        results = assess_dataset(cva6_requirements)
        metrics = aggregate_metrics(results)
        for key in ("total_requirements", "total_smells_detected", "gate_pass", "gate_fail"):
            assert key in metrics

    def test_total_matches_input(self, cva6_requirements):
        results = assess_dataset(cva6_requirements)
        metrics = aggregate_metrics(results)
        assert metrics["total_requirements"] == len(cva6_requirements)
