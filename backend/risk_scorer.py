"""
Step 4 — Risk Scorer
Input:  cell dicts (with raw_dependencies) + built DiGraph
Output: same cell dicts with risk_score (0–100) added in place

Scoring dimensions (total max = 100):
  1. Propagation risk   — descendants * 0.5,  capped at 35
  2. Terminal output    — is_terminal → +20
  3. Cross-sheet depth  — sheet_depth * 5,    capped at 15
  4. Symbol weight      — S=15, F=10, C=5
  5. Ancestor depth     — ancestors * 0.2,    capped at 10
  6. Cross-section bridge — cross-sheet ancestors AND has descendants → +5
"""

import logging

import networkx as nx

logger = logging.getLogger(__name__)

_SYMBOL_WEIGHT = {"S": 15, "F": 10, "C": 5}


def _is_bridge(node: tuple, G: nx.DiGraph) -> bool:
    """True if this node aggregates from another sheet AND has downstream dependents."""
    attrs = G.nodes.get(node, {})
    if not attrs.get("descendants"):
        return False
    ancestors = nx.ancestors(G, node) if node in G else set()
    return any(a[0] != node[0] for a in ancestors)


def score_cell(cell: dict, G: nx.DiGraph) -> float:
    """
    Input:  single cell dict, built DiGraph
    Output: risk score 0–100 (float, rounded to 2 dp)
    Only meaningful for F/S/C cells; N/X cells receive 0.
    """
    if cell["symbol"] not in ("F", "S", "C"):
        return 0.0

    node  = (cell["sheet"], cell["cell"])
    attrs = G.nodes.get(node, {})

    score = 0.0
    score += min(35.0, attrs.get("descendants", 0) * 0.5)
    score += 20.0 if attrs.get("is_terminal") else 0.0
    score += min(15.0, attrs.get("sheet_depth", 0) * 5.0)
    score += _SYMBOL_WEIGHT.get(cell["symbol"], 0)
    score += min(10.0, attrs.get("ancestors", 0) * 0.2)
    score += 5.0 if _is_bridge(node, G) else 0.0

    return round(score, 2)


def score_cells(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Input:  all cell dicts, built DiGraph
    Output: same list with risk_score added to each F/S/C cell (N/X get 0.0)
    Mutates cells in place and returns them.
    """
    for cell in cells:
        cell["risk_score"] = score_cell(cell, G)

    scored = [c for c in cells if c["symbol"] in ("F", "S", "C")]
    if scored:
        scores = [c["risk_score"] for c in scored]
        log_data = {
            "scored_cells": len(scored),
            "min_score":    round(min(scores), 2),
            "max_score":    round(max(scores), 2),
            "avg_score":    round(sum(scores) / len(scores), 2),
        }
        logger.info("[risk_scorer] Scoring complete: %s", log_data)

    return cells
