"""Tests for auto_flagger.py"""

import networkx as nx

from tests.conftest import make_cell, make_graph
from dependency_graph import build_graph
from auto_flagger import flag_x_in_chain, flag_circular_refs, flag_broken_refs, auto_flag


class TestFlagXInChain:
    def test_no_x_cells_returns_empty(self):
        cells = [make_cell(cell="A1", formula="=B1", symbol="F")]
        G = build_graph(cells)
        assert flag_x_in_chain(cells, G) == []

    def test_f_cell_depending_on_x_flagged(self):
        cells = [
            make_cell(cell="A1", formula="=B1", symbol="F"),
            make_cell(cell="B1", formula=None, symbol="X"),
        ]
        G = build_graph(cells)
        # mark tiers
        cells[0]["tier"] = 2
        cells[1]["tier"] = "AUTO"
        issues = flag_x_in_chain(cells, G)
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "x_in_chain"
        assert issues[0]["cell"] == "A1"

    def test_n_cell_depending_on_x_not_flagged(self):
        # N cells are not F/S/C so they shouldn't be flagged
        cells = [
            make_cell(cell="A1", formula=None, symbol="N"),
            make_cell(cell="B1", formula=None, symbol="X"),
        ]
        G = build_graph(cells)
        assert flag_x_in_chain(cells, G) == []

    def test_x_cell_itself_not_flagged(self):
        cells = [make_cell(cell="A1", symbol="X")]
        G = build_graph(cells)
        assert flag_x_in_chain(cells, G) == []


class TestFlagCircularRefs:
    def test_no_cycle_returns_empty(self):
        G = make_graph([("A", "B"), ("B", "C")])
        assert flag_circular_refs(G) == []

    def test_simple_cycle_detected(self):
        # A → B → A
        G = nx.DiGraph()
        G.add_edge(("Sheet1", "A1"), ("Sheet1", "B1"))
        G.add_edge(("Sheet1", "B1"), ("Sheet1", "A1"))
        issues = flag_circular_refs(G)
        assert len(issues) >= 1
        assert issues[0]["issue_type"] == "circular_ref"
        assert issues[0]["severity"] == "CRITICAL"

    def test_self_loop_detected(self):
        G = nx.DiGraph()
        G.add_edge(("Sheet1", "A1"), ("Sheet1", "A1"))
        issues = flag_circular_refs(G)
        assert len(issues) >= 1


class TestFlagBrokenRefs:
    def test_no_missing_refs_returns_empty(self):
        cells = [
            make_cell(cell="A1", formula="=B1", symbol="F"),
            make_cell(cell="B1", symbol="N"),
        ]
        G = build_graph(cells)
        assert flag_broken_refs(cells, G) == []

    def test_missing_ref_flagged(self):
        cells = [make_cell(cell="A1", formula="=Z99", symbol="F")]
        G = build_graph(cells)
        cells[0]["tier"] = 2
        issues = flag_broken_refs(cells, G)
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "broken_ref"
        assert issues[0]["cell"] == "A1"

    def test_n_x_cells_not_checked(self):
        cells = [
            make_cell(cell="A1", formula="=Z99", symbol="N"),
        ]
        cells[0]["raw_dependencies"] = [("Sheet1", "Z99")]
        G = build_graph(cells)
        assert flag_broken_refs(cells, G) == []


class TestAutoFlag:
    def test_returns_combined_issues(self):
        # X-in-chain + broken ref in one model
        cells = [
            make_cell(cell="A1", formula="=B1+Z99", symbol="F"),
            make_cell(cell="B1", symbol="X"),
        ]
        G = build_graph(cells)
        cells[0]["tier"] = 2
        cells[1]["tier"] = "AUTO"
        issues = auto_flag(cells, G)
        types = {i["issue_type"] for i in issues}
        assert "x_in_chain" in types
        assert "broken_ref" in types

    def test_clean_model_returns_empty(self):
        cells = [
            make_cell(cell="A1", formula="=B1", symbol="F"),
            make_cell(cell="B1", formula=None, symbol="N", value=10),
        ]
        G = build_graph(cells)
        cells[0]["tier"] = 3
        cells[1]["tier"] = "AUTO"
        assert auto_flag(cells, G) == []
