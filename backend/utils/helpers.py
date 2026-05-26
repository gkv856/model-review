"""
Shared utility functions used across the pipeline (DRY foundation).
"""

import json
import re
from typing import Iterator

from openpyxl.utils import get_column_letter

from utils.logger import get_logger

logger = get_logger(__name__)


def col_letter(col_idx: int) -> str:
    """Input: 1-based column index. Output: column letter (1→A, 27→AA)."""
    return get_column_letter(col_idx)


def make_issue(
    *,
    sheet: str,
    cell: str,
    symbol: str,
    tier: int | str,
    issue_type: str,
    severity: str,
    description: str,
    suggested_fix: str = "",
    label: str = "",
    section: str = "",
    period: str = "",
    formula: str = "",
    computed_value: object = None,
    instances: list | None = None,
) -> dict:
    """
    Input:  issue field values (all keyword-only to prevent ordering bugs)
    Output: fully-formed issue dict with instance_count set automatically
    """
    used_instances = instances if instances is not None else [cell]
    return {
        "sheet":          sheet,
        "cell":           cell,
        "label":          label or cell,
        "symbol":         symbol,
        "tier":           tier,
        "section":        section,
        "period":         period,
        "formula":        formula,
        "computed_value": computed_value,
        "issue_type":     issue_type,
        "severity":       severity,
        "description":    description,
        "suggested_fix":  suggested_fix,
        "instances":      used_instances,
        "instance_count": len(used_instances),
    }


def chunked(lst: list, size: int) -> Iterator[list]:
    """Input: list and chunk size. Output: iterator of sub-lists of at most `size` items."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_llm_json(text: str) -> list[dict]:
    """
    Input:  raw LLM text, may be wrapped in markdown fences
    Output: list of issue dicts from the 'issues' key; empty list on parse failure
    """
    fence_match = _JSON_FENCE_RE.search(text)
    clean = fence_match.group(1).strip() if fence_match else text.strip()
    try:
        data = json.loads(clean)
        return data.get("issues", [])
    except (json.JSONDecodeError, AttributeError):
        logger.error("[helpers] Failed to parse LLM JSON: %.200s", text)
        return []
