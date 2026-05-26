"""Tests for deduplicator.py"""

from tests.conftest import make_cell
from deduplicator import normalise_formula, deduplicate_by_pattern


class TestNormaliseFormula:
    def test_same_sheet_cell_refs_replaced(self):
        assert normalise_formula("=F15+F16") == "=REF+REF"

    def test_range_replaced(self):
        assert normalise_formula("=SUM(F15:F25)") == "=SUM(RANGE)"

    def test_cross_sheet_quoted_replaced(self):
        result = normalise_formula("='P&L'!F15+B2")
        assert "XSHEET!REF" in result
        assert "REF" in result

    def test_cross_sheet_bare_replaced(self):
        result = normalise_formula("=Sheet2!C10")
        assert "XSHEET!REF" in result

    def test_numeric_constants_replaced(self):
        assert normalise_formula("=F15*0.3") == "=REF*CONST"

    def test_empty_formula_returns_empty(self):
        assert normalise_formula("") == ""
        assert normalise_formula(None) == ""

    def test_complex_formula(self):
        result = normalise_formula("=SUM(F15:F20)/Sheet2!C10*1.1")
        assert "RANGE" in result
        assert "XSHEET!REF" in result
        assert "CONST" in result
        assert "SUM" in result

    def test_no_double_match_on_cross_sheet(self):
        # Cross-sheet ref stripped first — coord inside it should not also become REF
        result = normalise_formula("='P&L'!F15")
        assert result.count("XSHEET!REF") == 1
        assert "REF" not in result.replace("XSHEET!REF", "")


class TestDeduplicateByPattern:
    def _cell(self, coord: str, formula: str, score: float, symbol: str = "F") -> dict:
        return make_cell(cell=coord, formula=formula, symbol=symbol, risk_score=score)

    def test_identical_pattern_grouped(self):
        cells = [
            self._cell("A1", "=B1+C1", 60.0),
            self._cell("A2", "=B2+C2", 40.0),
        ]
        reps = deduplicate_by_pattern(cells)
        assert len(reps) == 1   # both share pattern =REF+REF

    def test_representative_is_highest_score(self):
        cells = [
            self._cell("A1", "=B1+C1", 60.0),
            self._cell("A2", "=B2+C2", 40.0),
        ]
        reps = deduplicate_by_pattern(cells)
        assert reps[0]["cell"] == "A1"   # score 60 > 40

    def test_pattern_instances_set_on_representative(self):
        cells = [
            self._cell("A1", "=B1+C1", 60.0),
            self._cell("A2", "=B2+C2", 40.0),
        ]
        reps = deduplicate_by_pattern(cells)
        rep = reps[0]
        assert rep["pattern_instance_count"] == 2
        assert ("Sheet1", "A2") in rep["pattern_instances"]

    def test_different_patterns_separate_groups(self):
        cells = [
            self._cell("A1", "=B1+C1", 50.0),
            self._cell("A2", "=SUM(B1:B5)", 50.0),
        ]
        reps = deduplicate_by_pattern(cells)
        assert len(reps) == 2

    def test_different_symbols_separate_groups(self):
        cells = [
            self._cell("A1", "=B1+C1", 50.0, symbol="F"),
            self._cell("A2", "=B2+C2", 50.0, symbol="S"),
        ]
        reps = deduplicate_by_pattern(cells)
        assert len(reps) == 2   # same pattern but different symbol

    def test_cells_without_formula_each_own_group(self):
        cells = [
            make_cell(cell="A1", formula=None, symbol="F", risk_score=50.0),
            make_cell(cell="A2", formula=None, symbol="F", risk_score=40.0),
        ]
        reps = deduplicate_by_pattern(cells)
        # Both normalise to "" and same symbol → grouped into one
        assert len(reps) == 1

    def test_single_cell_has_empty_instances(self):
        cells = [self._cell("A1", "=B1*C1", 55.0)]
        reps = deduplicate_by_pattern(cells)
        assert reps[0]["pattern_instances"] == []
        assert reps[0]["pattern_instance_count"] == 1
