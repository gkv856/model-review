"""
Step 4 — Risk Scorer
Input:  cell dicts + DiGraph
Output: same cells with risk_score (0–100) added in place

Scoring: descendants×0.5 (cap 35) + terminal +20 + sheet_depth×5 (cap 15)
       + symbol weight S=15/F=10/C=5 + ancestors×0.2 (cap 10) + bridge +5

Cells are scored in parallel chunks using ThreadPoolExecutor (65% CPU).
"""

import os
from concurrent.futures import ThreadPoolExecutor

import networkx as nx

from utils.helpers import chunked
from utils.logger import get_logger

logger = get_logger(__name__)

_MAX_WORKERS = max(1, int((os.cpu_count() or 1) * 0.65))
_SYMBOL_WEIGHT = {"S": 15, "F": 10, "C": 5}


def _is_bridge(node: tuple, G: nx.DiGraph) -> bool:
    """True if node aggregates from another sheet AND has downstream dependents."""
    attrs = G.nodes.get(node, {})
    if not attrs.get("descendants"):
        return False
    ancestors = nx.ancestors(G, node) if node in G else set()
    return any(a[0] != node[0] for a in ancestors)


def score_cell(cell: dict, G: nx.DiGraph) -> float:
    """
    Input:  single cell dict, built DiGraph
    Output: risk score 0–100 (float, rounded to 2 dp)
    N/X cells always return 0.
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


def _score_chunk(args: tuple) -> list[dict]:
    """Score a chunk of cells — runs in a worker thread."""
    cells_chunk, G = args
    for cell in cells_chunk:
        cell["risk_score"] = score_cell(cell, G)
    return cells_chunk


def score_cells(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Input:  all cell dicts, built DiGraph
    Output: same list with risk_score added (mutates in place)

    Cells are split into chunks and scored in parallel threads.
    """
    if not cells:
        return cells

    chunk_size = max(1, len(cells) // _MAX_WORKERS)
    chunks = list(chunked(cells, chunk_size))

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(chunks))) as pool:
        for scored_chunk in pool.map(_score_chunk, [(c, G) for c in chunks]):
            pass  # mutation happens in place; pool.map ensures all complete

    scored = [c for c in cells if c["symbol"] in ("F", "S", "C")]
    if scored:
        scores = [c["risk_score"] for c in scored]
        logger.info("[risk_scorer] Scored %d cells: min=%.2f max=%.2f avg=%.2f",
                    len(scored), min(scores), max(scores), sum(scores) / len(scores))

    return cells
