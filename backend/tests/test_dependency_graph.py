"""Tests for dependency_graph.py"""

import networkx as nx
import pytest

from tests.conftest import make_cell
from core.dependency_graph import extract_refs, build_graph, get_terminal_cells


class TestExtractRefs:
    def test_same_sheet_plain_ref(self):
        refs = extract_refs("=A1+B2", "Sheet1")
        assert ("Sheet1", "A1") in refs
        assert ("Sheet1", "B2") in refs

    def test_cross_sheet_quoted(self):
        refs = extract_refs("='P&L'!F15", "DCF")
        assert ("P&L", "F15") in refs

    def test_cross_sheet_bare(self):
        refs = extract_refs("=Sheet2!C10", "Sheet1")
        assert ("Sheet2", "C10") in refs

    def test_range_expansion(self):
        refs = extract_refs("=SUM(A1:A3)", "Sheet1")
        assert ("Sheet1", "A1") in refs
        assert ("Sheet1", "A2") in refs
        assert ("Sheet1", "A3") in refs

    def test_no_formula_returns_empty(self):
        assert extract_refs("100", "Sheet1") == []
        assert extract_refs("", "Sheet1") == []
        assert extract_refs(None, "Sheet1") == []

    def test_deduplicates_refs(self):
        refs = extract_refs("=A1+A1", "Sheet1")
        assert refs.count(("Sheet1", "A1")) == 1

    def test_mixed_formula(self):
        refs = extract_refs("='DCF'!B5 + SUM(A1:A3) + C1", "P&L")
        assert ("DCF", "B5") in refs
        assert ("P&L", "A1") in refs
        assert ("P&L", "C1") in refs


class TestBuildGraph:
    def test_nodes_created_for_all_cells(self):
        cells = [
            make_cell(cell="A1", formula="=B1+C1"),
            make_cell(cell="B1", formula=None, value=10, symbol="N"),
            make_cell(cell="C1", formula=None, value=20, symbol="N"),
        ]
        G = build_graph(cells)
        assert ("Sheet1", "A1") in G.nodes

    def test_edges_direction_correct(self):
        # A1 depends on B1  →  edge B1 → A1
        cells = [make_cell(cell="A1", formula="=B1*2")]
        G = build_graph(cells)
        assert G.has_edge(("Sheet1", "B1"), ("Sheet1", "A1"))

    def test_raw_dependencies_written_to_cell(self):
        cells = [make_cell(cell="A1", formula="=B1+C1")]
        build_graph(cells)
        assert ("Sheet1", "B1") in cells[0]["raw_dependencies"]

    def test_is_terminal_for_leaf_node(self):
        # A1 = B1 + C1. B1 and C1 have nothing depending on them → not terminal.
        # A1 has nothing depending on it → terminal.
        cells = [
            make_cell(cell="A1", formula="=B1+C1"),
            make_cell(cell="B1", formula=None, value=5, symbol="N"),
        ]
        G = build_graph(cells)
        assert G.nodes[("Sheet1", "A1")]["is_terminal"] is True
        assert G.nodes[("Sheet1", "B1")]["is_terminal"] is False

    def test_descendants_count(self):
        # Chain: C1 → B1 → A1  (A1 depends on B1, B1 depends on C1)
        cells = [
            make_cell(cell="A1", formula="=B1"),
            make_cell(cell="B1", formula="=C1"),
        ]
        G = build_graph(cells)
        # C1 has descendants: B1 and A1 → 2
        assert G.nodes[("Sheet1", "C1")]["descendants"] == 2


class TestGetTerminalCells:
    def test_returns_only_terminal_whitelist_cells(self):
        cells = [
            make_cell(cell="A1", formula="=B1"),   # depends on B1
            make_cell(cell="B1", formula="=C1"),   # depends on C1
        ]
        G = build_graph(cells)
        terminal = get_terminal_cells(cells, G)
        terminal_coords = {c["cell"] for c in terminal}
        assert "A1" in terminal_coords   # nothing depends on A1
        assert "B1" not in terminal_coords
