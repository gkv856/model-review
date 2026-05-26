"""
Step 8 — Tier 3 Rule-Based Checker
Input:  all cell dicts (tier assigned) + built DiGraph
Output: list[dict] of issues for Tier 3 cells only

Five deterministic checks; no LLM. Each check_* returns a single issue dict or None.
"""

import logging
from collections import Counter

import networkx as nx

from utils import make_issue

logger = logging.getLogger(__name__)


def check_divide_by_zero_risk(cell: dict, G: nx.DiGraph) -> dict | None:
    """Flag if formula contains division and any direct predecessor value is zero/near-zero."""
    formula = cell.get("formula") or ""
    if "/" not in formula:
        return None

    node = (cell["sheet"], cell["cell"])
    predecessors = list(G.predecessors(node)) if node in G else []

    for pred in predecessors:
        pred_attrs = G.nodes.get(pred, {})
        val = pred_attrs.get("value")
        if val is None:
            continue
        try:
            numeric = float(val)
        except (TypeError, ValueError):
            continue
        if abs(numeric) < 1e-9:
            return make_issue(
                sheet=cell["sheet"],
                cell=cell["cell"],
                label=cell.get("label", ""),
                symbol=cell["symbol"],
                tier=cell.get("tier", 3),
                issue_type="divide_by_zero_risk",
                severity="WARNING",
                description=(
                    f"Formula contains division and predecessor {pred[1]} has value ≈ 0. "
                    "May cause #DIV/0! error at runtime."
                ),
                suggested_fix="Add an IFERROR or IF guard around the division.",
            )
    return None


def check_hardcoded_mid_chain(cell: dict, G: nx.DiGraph) -> dict | None:
    """Flag if a hardcoded (N) cell feeds this formula cell AND this cell has dependents."""
    node = (cell["sheet"], cell["cell"])
    attrs = G.nodes.get(node, {})

    if not attrs.get("descendants"):
        return None   # terminal — hardcoded input at end is fine

    predecessors = list(G.predecessors(node)) if node in G else []
    n_preds = [p for p in predecessors if G.nodes.get(p, {}).get("symbol") == "N"]
    if not n_preds:
        return None

    return make_issue(
        sheet=cell["sheet"],
        cell=cell["cell"],
        label=cell.get("label", ""),
        symbol=cell["symbol"],
        tier=cell.get("tier", 3),
        issue_type="hardcoded_mid_chain",
        severity="WARNING",
        description=(
            f"Hardcoded cell(s) {[p[1] for p in n_preds]} feed into this formula "
            "which itself has downstream dependents. A hardcoded mid-chain value is fragile."
        ),
        suggested_fix="Move the hardcoded value to a dedicated assumptions tab and reference it.",
    )


def check_self_reference(cell: dict, G: nx.DiGraph) -> dict | None:
    """Flag if the cell's own coordinate appears in its raw_dependencies."""
    node = (cell["sheet"], cell["cell"])
    if node in cell.get("raw_dependencies", []):
        return make_issue(
            sheet=cell["sheet"],
            cell=cell["cell"],
            label=cell.get("label", ""),
            symbol=cell["symbol"],
            tier=cell.get("tier", 3),
            issue_type="self_reference",
            severity="CRITICAL",
            description=f"Cell {cell['cell']} references itself in its formula.",
            suggested_fix="Remove the self-reference and restructure the calculation.",
        )
    return None


def check_empty_sum_range(cell: dict, G: nx.DiGraph) -> dict | None:
    """Flag S-type cells whose value and all direct predecessor values are 0 or None."""
    if cell.get("symbol") != "S":
        return None

    cell_val = cell.get("value")
    if cell_val not in (0, None) and cell_val != 0.0:
        return None

    node = (cell["sheet"], cell["cell"])
    predecessors = list(G.predecessors(node)) if node in G else []
    if not predecessors:
        return None

    all_empty = all(
        G.nodes.get(p, {}).get("value") in (0, None, 0.0)
        for p in predecessors
    )
    if not all_empty:
        return None

    return make_issue(
        sheet=cell["sheet"],
        cell=cell["cell"],
        label=cell.get("label", ""),
        symbol=cell["symbol"],
        tier=cell.get("tier", 3),
        issue_type="empty_sum_range",
        severity="INFO",
        description=(
            "SUM cell and all its predecessors are 0 or empty. "
            "May be summing an unfilled range or a placeholder row."
        ),
        suggested_fix="Verify the summed range contains the expected data.",
    )


def check_unit_mismatch_heuristic(cell: dict, G: nx.DiGraph) -> dict | None:
    """
    Flag if this cell has a units field and its units differ from the majority
    of its direct predecessors. Skipped when units is not populated.
    """
    cell_units = cell.get("units")
    if not cell_units:
        return None

    node = (cell["sheet"], cell["cell"])
    predecessors = list(G.predecessors(node)) if node in G else []
    if not predecessors:
        return None

    pred_units = [
        G.nodes.get(p, {}).get("units")
        for p in predecessors
        if G.nodes.get(p, {}).get("units")
    ]
    if not pred_units:
        return None

    majority_unit, _ = Counter(pred_units).most_common(1)[0]
    if cell_units == majority_unit:
        return None

    return make_issue(
        sheet=cell["sheet"],
        cell=cell["cell"],
        label=cell.get("label", ""),
        symbol=cell["symbol"],
        tier=cell.get("tier", 3),
        issue_type="unit_mismatch",
        severity="WARNING",
        description=(
            f"Cell unit '{cell_units}' differs from majority predecessor unit '{majority_unit}'. "
            "Formula may be mixing incompatible units."
        ),
        suggested_fix="Verify unit consistency across the formula inputs.",
    )


RULE_CHECKS = [
    check_divide_by_zero_risk,
    check_hardcoded_mid_chain,
    check_self_reference,
    check_empty_sum_range,
    check_unit_mismatch_heuristic,
]


def run_tier3_checks(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Input:  all cell dicts (tier assigned), built DiGraph
    Output: issues list for Tier 3 cells only
    """
    issues: list[dict] = []
    tier3 = [c for c in cells if c.get("tier") == 3]

    for cell in tier3:
        for check_fn in RULE_CHECKS:
            result = check_fn(cell, G)
            if result:
                issues.append(result)

    logger.info(
        "[tier3_checker] Checked %d tier-3 cells, found %d issues",
        len(tier3), len(issues),
    )
    return issues
