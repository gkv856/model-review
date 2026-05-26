"""Tests for risk_scorer.py"""

import networkx as nx

from tests.conftest import make_cell, make_graph
from core.dependency_graph import build_graph
from core.risk_scorer import score_cell, score_cells


class TestScoreCell:
    def test_n_x_cells_score_zero(self):
        G = nx.DiGraph()
        for sym in ("N", "X"):
            cell = make_cell(symbol=sym)
            assert score_cell(cell, G) == 0.0

    def test_terminal_node_gets_bonus(self):
        # A1 depends on B1; A1 is terminal
        cells = [
            make_cell(cell="A1", formula="=B1", symbol="F"),
            make_cell(cell="B1", formula=None, symbol="N", value=5),
        ]
        G = build_graph(cells)
        score = score_cell(cells[0], G)
        assert score >= 20.0   # terminal bonus applied

    def test_symbol_weight_s_higher_than_f(self):
        cells_s = [make_cell(cell="A1", formula="=SUM(B1:B5)", symbol="S")]
        cells_f = [make_cell(cell="A1", formula="=B1*C1",     symbol="F")]
        G_s = build_graph(cells_s)
        G_f = build_graph(cells_f)
        # Both isolated (same topology), S should score higher
        assert score_cell(cells_s[0], G_s) > score_cell(cells_f[0], G_f)

    def test_more_descendants_higher_score(self):
        # Chain: C1 → B1 → A1
        # C1 has 2 descendants (B1, A1); B1 has 1 descendant (A1)
        # Neither is terminal → pure descendant count drives the gap
        chain_cells = [
            make_cell(cell="A1", formula="=B1", symbol="F"),
            make_cell(cell="B1", formula="=C1", symbol="F"),
        ]
        G = build_graph(chain_cells)
        c1 = {"sheet": "Sheet1", "cell": "C1", "symbol": "F"}
        b1 = {"sheet": "Sheet1", "cell": "B1", "symbol": "F"}
        assert score_cell(c1, G) > score_cell(b1, G)

    def test_score_bounded_0_to_100(self):
        cells = [make_cell(cell="A1", formula="=B1", symbol="S")]
        G = build_graph(cells)
        score = score_cell(cells[0], G)
        assert 0.0 <= score <= 100.0


class TestScoreCells:
    def test_mutates_cells_in_place(self):
        cells = [make_cell(symbol="F")]
        G = build_graph(cells)
        result = score_cells(cells, G)
        assert "risk_score" in cells[0]
        assert result is cells   # same list object returned

    def test_all_cells_get_risk_score(self):
        cells = [
            make_cell(cell="A1", symbol="F"),
            make_cell(cell="B1", symbol="N"),
        ]
        G = build_graph(cells)
        score_cells(cells, G)
        for cell in cells:
            assert "risk_score" in cell
