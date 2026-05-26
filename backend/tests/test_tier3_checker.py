"""Tests for tier3_checker.py"""

import networkx as nx

from tests.conftest import make_cell
from dependency_graph import build_graph
from tier3_checker import (
    check_divide_by_zero_risk,
    check_hardcoded_mid_chain,
    check_self_reference,
    check_empty_sum_range,
    check_unit_mismatch_heuristic,
    run_tier3_checks,
)


def _t3(cell_dict: dict) -> dict:
    cell_dict["tier"] = 3
    return cell_dict


class TestDivideByZeroRisk:
    def test_flags_when_predecessor_zero(self):
        cells = [
            _t3(make_cell(cell="A1", formula="=B1/C1", symbol="F")),
            make_cell(cell="B1", symbol="N", value=10),
            make_cell(cell="C1", symbol="N", value=0),
        ]
        G = build_graph(cells)
        # Store value on graph node so checker can read it
        G.nodes[("Sheet1", "C1")]["value"] = 0
        result = check_divide_by_zero_risk(cells[0], G)
        assert result is not None
        assert result["issue_type"] == "divide_by_zero_risk"
        assert result["severity"] == "WARNING"

    def test_no_flag_when_no_division(self):
        cells = [_t3(make_cell(cell="A1", formula="=B1+C1", symbol="F"))]
        G = build_graph(cells)
        assert check_divide_by_zero_risk(cells[0], G) is None

    def test_no_flag_when_predecessors_nonzero(self):
        cells = [
            _t3(make_cell(cell="A1", formula="=B1/C1", symbol="F")),
            make_cell(cell="C1", symbol="N", value=5),
        ]
        G = build_graph(cells)
        G.nodes[("Sheet1", "C1")]["value"] = 5
        assert check_divide_by_zero_risk(cells[0], G) is None


class TestHardcodedMidChain:
    def test_flags_n_predecessor_with_dependents(self):
        # Chain: C1(N) → B1(F) → A1(F); B1 has descendants so is mid-chain
        cells = [
            _t3(make_cell(cell="A1", formula="=B1", symbol="F")),
            _t3(make_cell(cell="B1", formula="=C1", symbol="F")),
            make_cell(cell="C1", symbol="N", value=5),
        ]
        G = build_graph(cells)
        G.nodes[("Sheet1", "C1")]["symbol"] = "N"
        # B1 has A1 as dependent → has descendants
        result = check_hardcoded_mid_chain(cells[1], G)
        assert result is not None
        assert result["issue_type"] == "hardcoded_mid_chain"

    def test_no_flag_when_terminal(self):
        # B1(F) depends on C1(N) but nothing depends on B1 → terminal, ok
        cells = [
            _t3(make_cell(cell="B1", formula="=C1", symbol="F")),
            make_cell(cell="C1", formula=None, symbol="N", value=5),  # no formula — leaf
        ]
        G = build_graph(cells)
        G.nodes[("Sheet1", "C1")]["symbol"] = "N"
        assert check_hardcoded_mid_chain(cells[0], G) is None

    def test_no_flag_when_no_n_predecessor(self):
        cells = [
            _t3(make_cell(cell="A1", formula="=B1", symbol="F")),
            _t3(make_cell(cell="B1", formula="=C1", symbol="F")),
        ]
        G = build_graph(cells)
        assert check_hardcoded_mid_chain(cells[1], G) is None


class TestSelfReference:
    def test_flags_self_dep(self):
        cell = _t3(make_cell(cell="A1", formula="=A1+1", symbol="F"))
        cell["raw_dependencies"] = [("Sheet1", "A1")]
        G = build_graph([cell])
        result = check_self_reference(cell, G)
        assert result is not None
        assert result["issue_type"] == "self_reference"
        assert result["severity"] == "CRITICAL"

    def test_no_flag_when_clean(self):
        cell = _t3(make_cell(cell="A1", formula="=B1", symbol="F"))
        G = build_graph([cell])
        assert check_self_reference(cell, G) is None


class TestEmptySumRange:
    def test_flags_sum_cell_all_zeros(self):
        cells = [
            _t3(make_cell(cell="A1", formula="=SUM(B1:B3)", symbol="S", value=0)),
            make_cell(cell="B1", symbol="N", value=0),
            make_cell(cell="B2", symbol="N", value=0),
        ]
        G = build_graph(cells)
        G.nodes[("Sheet1", "B1")]["value"] = 0
        G.nodes[("Sheet1", "B2")]["value"] = 0
        result = check_empty_sum_range(cells[0], G)
        assert result is not None
        assert result["issue_type"] == "empty_sum_range"

    def test_no_flag_when_predecessor_nonzero(self):
        cells = [
            _t3(make_cell(cell="A1", formula="=SUM(B1:B2)", symbol="S", value=5)),
        ]
        G = build_graph(cells)
        assert check_empty_sum_range(cells[0], G) is None

    def test_no_flag_when_not_s_symbol(self):
        cell = _t3(make_cell(cell="A1", formula="=B1", symbol="F", value=0))
        G = build_graph([cell])
        assert check_empty_sum_range(cell, G) is None


class TestUnitMismatch:
    def test_flags_when_units_differ(self):
        cell = _t3(make_cell(cell="A1", formula="=B1+C1", symbol="F"))
        cell["units"] = "USD"
        cells = [
            cell,
            make_cell(cell="B1", symbol="N"),
            make_cell(cell="C1", symbol="N"),
        ]
        G = build_graph(cells)
        G.nodes[("Sheet1", "B1")]["units"] = "%"
        G.nodes[("Sheet1", "C1")]["units"] = "%"
        result = check_unit_mismatch_heuristic(cell, G)
        assert result is not None
        assert result["issue_type"] == "unit_mismatch"

    def test_no_flag_when_units_match(self):
        cell = _t3(make_cell(cell="A1", formula="=B1+C1", symbol="F"))
        cell["units"] = "USD"
        cells = [cell, make_cell(cell="B1", symbol="N")]
        G = build_graph(cells)
        G.nodes[("Sheet1", "B1")]["units"] = "USD"
        assert check_unit_mismatch_heuristic(cell, G) is None

    def test_no_flag_when_no_units_field(self):
        cell = _t3(make_cell(cell="A1", formula="=B1", symbol="F"))
        G = build_graph([cell])
        assert check_unit_mismatch_heuristic(cell, G) is None


class TestRunTier3Checks:
    def test_only_tier3_cells_checked(self):
        cells = [
            make_cell(cell="A1", formula="=A1+1", symbol="F"),   # tier 1 — not checked
            _t3(make_cell(cell="B1", formula="=B1+1", symbol="F")),
        ]
        cells[0]["tier"] = 1
        cells[0]["raw_dependencies"] = [("Sheet1", "A1")]
        cells[1]["raw_dependencies"] = [("Sheet1", "B1")]
        G = build_graph(cells)
        issues = run_tier3_checks(cells, G)
        cells_in_issues = {i["cell"] for i in issues}
        assert "A1" not in cells_in_issues   # tier 1, skipped
        assert "B1" in cells_in_issues       # tier 3, self-ref flagged
