"""Tests for llm_reviewer.py — mocks the LLM to avoid real API calls."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tests.conftest import make_cell
from llm.reviewer import (
    review_tier1,
    review_tier2,
    review_cross_section,
    run_llm_review,
    _build_tier1_user_prompt,
    _build_tier2_user_prompt,
    _group_by_sheet_section,
)


def _enriched(cell: str = "A1", sheet: str = "Sheet1", section: str = "Revenue",
               is_terminal: bool = False, formula: str = "=B1+C1") -> dict:
    c = make_cell(cell=cell, formula=formula)
    c["sheet"] = sheet
    c["label"] = f"Label {cell}"
    c["units"] = "USD"
    c["period"] = "FY2025"
    c["section"] = section
    c["is_terminal"] = is_terminal
    c["dependencies"] = []
    return c


def _mock_llm_response(issues: list[dict]):
    """Return a mock LLM that responds with the given issues."""
    import json
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({"issues": issues})
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


class TestBuildPrompts:
    def test_tier1_prompt_includes_label(self):
        cell = _enriched()
        prompt = _build_tier1_user_prompt([cell])
        assert "Label A1" in prompt
        assert "Sheet1" in prompt

    def test_tier2_prompt_is_concise(self):
        cell = _enriched()
        prompt = _build_tier2_user_prompt([cell])
        assert "Label A1" in prompt
        assert "dependencies" not in prompt.lower()


class TestGroupBySheetSection:
    def test_groups_correctly(self):
        cells = [
            _enriched("A1", "Sheet1", "Revenue"),
            _enriched("B1", "Sheet1", "Revenue"),
            _enriched("C1", "Sheet1", "Costs"),
        ]
        groups = _group_by_sheet_section(cells)
        assert len(groups[("Sheet1", "Revenue")]) == 2
        assert len(groups[("Sheet1", "Costs")]) == 1


class TestReviewTier1:
    async def test_returns_issues_and_call_count(self):
        cells = [_enriched("A1"), _enriched("B1")]
        mock_issue = {"sheet": "Sheet1", "cell": "A1", "issue_type": "SIGN_ERROR", "severity": "CRITICAL"}

        with patch("llm.reviewer.get_llm", return_value=_mock_llm_response([mock_issue])):
            issues, calls = await review_tier1(cells)

        assert calls >= 1
        assert any(i["issue_type"] == "SIGN_ERROR" for i in issues)

    async def test_empty_cells_returns_no_calls(self):
        issues, calls = await review_tier1([])
        assert issues == []
        assert calls == 0


class TestReviewTier2:
    async def test_returns_issues_and_call_count(self):
        cells = [_enriched(f"A{i}") for i in range(5)]
        mock_issue = {"sheet": "Sheet1", "cell": "A1", "issue_type": "WRONG_OPERATOR", "severity": "WARNING"}

        with patch("llm.reviewer.get_llm", return_value=_mock_llm_response([mock_issue])):
            issues, calls = await review_tier2(cells)

        assert calls == 1   # 5 cells fits in one batch of 50
        assert len(issues) >= 1

    async def test_empty_cells_returns_no_calls(self):
        issues, calls = await review_tier2([])
        assert issues == []
        assert calls == 0


class TestReviewCrossSection:
    async def test_skipped_with_fewer_than_two_terminals(self):
        issues, calls = await review_cross_section([_enriched(is_terminal=True)])
        assert calls == 0

    async def test_runs_with_two_or_more_terminals(self):
        terminals = [_enriched("A1", is_terminal=True), _enriched("B1", is_terminal=True)]
        mock_issue = {"sheet": "Sheet1", "cell": "A1", "issue_type": "CROSS_SECTION_INCONSISTENCY", "severity": "WARNING"}

        with patch("llm.reviewer.get_llm", return_value=_mock_llm_response([mock_issue])):
            issues, calls = await review_cross_section(terminals)

        assert calls == 1
        assert len(issues) == 1


class TestRunLlmReview:
    async def test_orchestrates_all_passes(self):
        t1 = [_enriched("A1", is_terminal=True)]
        t2 = [_enriched("B1")]

        with patch("llm.reviewer.get_llm", return_value=_mock_llm_response([])):
            result = await run_llm_review(t1, t2)

        assert "issues" in result
        assert "llm_calls" in result
        assert isinstance(result["llm_calls"], int)

    async def test_retry_on_llm_failure(self):
        cells = [_enriched("A1")]

        # First call raises, second returns empty
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"issues": []}'
        mock_llm.ainvoke = AsyncMock(side_effect=[Exception("timeout"), mock_response])

        with patch("llm.reviewer.get_llm", return_value=mock_llm):
            with patch("llm.reviewer.asyncio.sleep", new_callable=AsyncMock):
                issues, calls = await review_tier1(cells)

        assert calls == 1   # completed on retry
        assert issues == []
