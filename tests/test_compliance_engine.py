"""Unit tests for the compliance constraint engine."""


from specguard.compliance import (
    CROSS_DOMAIN_OBJECTIVES,
    DO_178C_OBJECTIVES,
    DO_254_OBJECTIVES,
    ComplianceReport,
    run_compliance_check,
)


class TestObjectiveCatalogs:
    def test_do178c_count(self):
        assert len(DO_178C_OBJECTIVES) == 7

    def test_do254_count(self):
        assert len(DO_254_OBJECTIVES) == 5

    def test_cross_domain_count(self):
        assert len(CROSS_DOMAIN_OBJECTIVES) == 3

    def test_objectives_have_ids(self):
        for obj in DO_178C_OBJECTIVES + DO_254_OBJECTIVES + CROSS_DOMAIN_OBJECTIVES:
            assert obj.objective_id, "Objective missing an id"
            assert obj.cypher_query, "Objective missing a cypher_query"


class TestRunComplianceCheck:
    def _no_op_runner(self, query, params):
        return []

    def test_returns_compliance_report(self):
        report = run_compliance_check(self._no_op_runner, DO_178C_OBJECTIVES)
        assert isinstance(report, ComplianceReport)

    def test_no_violations_with_no_op_runner(self):
        report = run_compliance_check(self._no_op_runner, DO_178C_OBJECTIVES)
        assert report.violation_count == 0
        assert report.total_objectives_checked == len(DO_178C_OBJECTIVES)
        assert len(report.passing_objective_ids) == len(DO_178C_OBJECTIVES)

    def test_violations_are_captured(self):
        def always_violating(query, params):
            return [{"violating_requirement": "REQ-1", "req_text": "text", "reason": "test"}]

        report = run_compliance_check(always_violating, DO_178C_OBJECTIVES[:1])
        assert report.violation_count >= 1
