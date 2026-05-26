"""Tests for report_generator.py"""

from tests.conftest import make_cell
from reporting.generator import build_json_report, build_html_report


def _make_cells():
    return [
        {**make_cell(cell="A1", symbol="F"), "tier": 1},
        {**make_cell(cell="B1", symbol="S"), "tier": 2},
        {**make_cell(cell="C1", symbol="N"), "tier": "AUTO"},
    ]


def _make_issue(cell: str = "A1", sev: str = "CRITICAL", issue_type: str = "SIGN_ERROR") -> dict:
    return {
        "sheet": "Sheet1", "cell": cell, "label": "Revenue",
        "symbol": "F", "tier": 1,
        "issue_type": issue_type, "severity": sev,
        "description": "Test description",
        "suggested_fix": "Test fix",
        "instances": [("Sheet1", cell)],
        "instance_count": 1,
    }


class TestBuildJsonReport:
    def test_has_required_top_level_keys(self):
        report = build_json_report(
            job_id="test123",
            model_filename="model.xlsx",
            map_filename="map.xlsx",
            cells=_make_cells(),
            issues=[_make_issue()],
            auto_issues=[],
            llm_calls_made=5,
            patterns_reviewed=10,
        )
        for key in ("job_id", "model_filename", "map_filename", "reviewed_at",
                    "summary", "graph_analysis", "issues"):
            assert key in report

    def test_summary_counts_correct(self):
        report = build_json_report(
            job_id="j1",
            model_filename="m.xlsx",
            map_filename="map.xlsx",
            cells=_make_cells(),
            issues=[_make_issue(sev="CRITICAL"), _make_issue("B1", "WARNING")],
            auto_issues=[_make_issue("C1", "INFO", "hardcoded")],
            llm_calls_made=3,
            patterns_reviewed=8,
        )
        s = report["summary"]
        assert s["total_issues"] == 3
        assert s["critical"] == 1
        assert s["warning"] == 1
        assert s["info"] == 1
        assert s["llm_calls_made"] == 3
        assert s["patterns_reviewed"] == 8

    def test_issues_sorted_by_severity(self):
        report = build_json_report(
            job_id="j1", model_filename="m.xlsx", map_filename="map.xlsx",
            cells=_make_cells(),
            issues=[_make_issue("B1", "INFO"), _make_issue("A1", "CRITICAL")],
            auto_issues=[],
            llm_calls_made=0, patterns_reviewed=0,
        )
        sevs = [i["severity"] for i in report["issues"]]
        assert sevs[0] == "CRITICAL"
        assert sevs[-1] == "INFO"

    def test_graph_analysis_populated(self):
        auto = [{
            "sheet": "Sheet1", "cell": "A1", "label": "", "symbol": "F",
            "tier": "AUTO", "issue_type": "circular_ref", "severity": "CRITICAL",
            "description": "", "suggested_fix": "",
        }]
        report = build_json_report(
            job_id="j1", model_filename="m.xlsx", map_filename="map.xlsx",
            cells=_make_cells(), issues=[], auto_issues=auto,
            llm_calls_made=0, patterns_reviewed=0,
        )
        assert "Sheet1!A1" in report["graph_analysis"]["circular_references"]

    def test_tier_breakdown_counts(self):
        report = build_json_report(
            job_id="j1", model_filename="m.xlsx", map_filename="map.xlsx",
            cells=_make_cells(), issues=[], auto_issues=[],
            llm_calls_made=0, patterns_reviewed=0,
        )
        tb = report["summary"]["tier_breakdown"]
        assert tb["tier1"] == 1
        assert tb["tier2"] == 1
        assert tb["auto"] == 1


class TestBuildHtmlReport:
    def _base_report(self):
        return build_json_report(
            job_id="j1", model_filename="model.xlsx", map_filename="map.xlsx",
            cells=_make_cells(),
            issues=[_make_issue()],
            auto_issues=[],
            llm_calls_made=2, patterns_reviewed=5,
        )

    def test_returns_valid_html_string(self):
        html = build_html_report(self._base_report())
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_no_cdn_links(self):
        html = build_html_report(self._base_report())
        assert "cdn." not in html
        assert "https://" not in html

    def test_model_filename_in_html(self):
        html = build_html_report(self._base_report())
        assert "model.xlsx" in html

    def test_issue_type_in_html(self):
        html = build_html_report(self._base_report())
        assert "SIGN_ERROR" in html
