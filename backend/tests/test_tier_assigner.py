"""Tests for tier_assigner.py"""

from tests.conftest import make_cell
from core.tier_assigner import assign_tiers


def _make_scored_cells(scores: list[float], symbol: str = "F") -> list[dict]:
    return [
        make_cell(cell=f"A{i+1}", symbol=symbol, risk_score=s)
        for i, s in enumerate(scores)
    ]


class TestAssignTiers:
    def test_n_x_cells_get_auto_tier(self):
        cells = [make_cell(symbol="N"), make_cell(symbol="X")]
        result = assign_tiers(cells)
        for cell in result:
            assert cell["tier"] == "AUTO"

    def test_tier_distribution_proportional(self):
        # 20 cells with linearly spaced scores → expect roughly 3/7/10 split
        scores = [float(i * 5) for i in range(20)]  # 0, 5, 10, ... 95
        cells = _make_scored_cells(scores)
        assign_tiers(cells)

        tier1 = [c for c in cells if c["tier"] == 1]
        tier3 = [c for c in cells if c["tier"] == 3]

        # Top 15% of 20 = 3 cells in tier 1
        assert len(tier1) == 3
        # Bottom 50% of 20 = 10 cells in tier 3
        assert len(tier3) == 10

    def test_all_cells_get_tier(self):
        cells = _make_scored_cells([10.0, 50.0, 90.0])
        assign_tiers(cells)
        for cell in cells:
            assert "tier" in cell
            assert cell["tier"] in (1, 2, 3)

    def test_flat_distribution_falls_back_to_fixed(self):
        # All same score → std ≈ 0 → fallback thresholds
        cells = _make_scored_cells([50.0, 50.0, 50.0, 50.0])
        assign_tiers(cells)  # should not raise
        for cell in cells:
            assert "tier" in cell

    def test_higher_score_gets_lower_tier_number(self):
        # Tier 1 = highest risk
        cells = _make_scored_cells([0.0, 50.0, 100.0])
        assign_tiers(cells)
        tiers = [c["tier"] for c in cells]
        assert tiers[2] <= tiers[1] <= tiers[0]   # scores asc → tiers desc

    def test_mutates_in_place(self):
        cells = _make_scored_cells([20.0, 80.0])
        result = assign_tiers(cells)
        assert result is cells
