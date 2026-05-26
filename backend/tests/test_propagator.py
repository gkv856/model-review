"""Tests for propagator.py"""

from reporting.propagator import propagate_findings


def _issue(sheet: str = "Sheet1", cell: str = "A1") -> dict:
    return {"sheet": sheet, "cell": cell, "severity": "WARNING", "issue_type": "SIGN_ERROR"}


def _rep(sheet: str = "Sheet1", cell: str = "A1", instances: list | None = None) -> dict:
    return {
        "sheet": sheet,
        "cell":  cell,
        "pattern_instances": instances or [],
        "pattern_instance_count": 1 + len(instances or []),
    }


class TestPropagateFinding:
    def test_propagates_to_pattern_instances(self):
        issues = [_issue("Sheet1", "A1")]
        reps = [_rep("Sheet1", "A1", instances=[("Sheet1", "A2"), ("Sheet1", "A3")])]
        propagate_findings(issues, reps)
        assert issues[0]["instance_count"] == 3
        assert ("Sheet1", "A2") in issues[0]["instances"]

    def test_no_match_gets_count_one(self):
        issues = [_issue("Sheet1", "Z99")]
        reps = [_rep("Sheet1", "A1")]
        propagate_findings(issues, reps)
        assert issues[0]["instance_count"] == 1

    def test_rep_with_no_instances_stays_count_one(self):
        issues = [_issue("Sheet1", "A1")]
        reps = [_rep("Sheet1", "A1", instances=[])]
        propagate_findings(issues, reps)
        assert issues[0]["instance_count"] == 1

    def test_mutates_in_place_returns_same_list(self):
        issues = [_issue()]
        reps = [_rep()]
        result = propagate_findings(issues, reps)
        assert result is issues

    def test_multiple_issues_multiple_reps(self):
        issues = [_issue("Sheet1", "A1"), _issue("Sheet1", "B1")]
        reps = [
            _rep("Sheet1", "A1", instances=[("Sheet1", "A2")]),
            _rep("Sheet1", "B1", instances=[]),
        ]
        propagate_findings(issues, reps)
        assert issues[0]["instance_count"] == 2
        assert issues[1]["instance_count"] == 1
