"""
Step 3 — Dependency Graph Builder
Input:  list of cell dicts from model_parser
Output: networkx DiGraph + raw_dependencies stored on each cell dict

Edge direction: dependency → dependent
  A1 feeds C1  →  edge (Sheet1, A1) → (Sheet1, C1)

Node metrics: out_degree, in_degree, is_terminal, sheet_depth, ancestors, descendants
"""

import re
from concurrent.futures import ThreadPoolExecutor
import os

import networkx as nx
from openpyxl.utils import column_index_from_string, get_column_letter

from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RANGE_CELLS = 200
_MAX_WORKERS = max(1, int((os.cpu_count() or 1) * 0.65))

_CROSS_QUOTED_RE = re.compile(r"'([^']+)'!\$?([A-Z]+)\$?(\d+)", re.IGNORECASE)
_CROSS_BARE_RE   = re.compile(r"(?<!['])([A-Za-z0-9_]+)!\$?([A-Z]+)\$?(\d+)", re.IGNORECASE)
_RANGE_RE        = re.compile(r"(?<!!)(\$?[A-Z]+)\$?(\d+):(\$?[A-Z]+)\$?(\d+)", re.IGNORECASE)
_CELL_RE         = re.compile(r"(?<![!A-Za-z])(\$?[A-Z]+)\$?(\d+)(?![A-Za-z])")


def _expand_range(sheet: str, col1: str, row1: int, col2: str, row2: int) -> list[tuple[str, str]]:
    c1 = column_index_from_string(col1.lstrip("$"))
    c2 = column_index_from_string(col2.lstrip("$"))
    refs: list[tuple[str, str]] = []
    for r in range(row1, row2 + 1):
        for c in range(c1, c2 + 1):
            refs.append((sheet, f"{get_column_letter(c)}{r}"))
            if len(refs) >= MAX_RANGE_CELLS:
                return refs
    return refs


def extract_refs(formula: str, current_sheet: str) -> list[tuple[str, str]]:
    """
    Input:  formula string (must start with '='), current sheet name
    Output: deduplicated list of (sheet, cell_coord) tuples this formula references
    """
    if not formula or not formula.startswith("="):
        return []

    refs: list[tuple[str, str]] = []

    for sheet, col, row in _CROSS_QUOTED_RE.findall(formula):
        refs.append((sheet, f"{col.upper()}{row}"))
    for sheet, col, row in _CROSS_BARE_RE.findall(formula):
        refs.append((sheet, f"{col.upper()}{row}"))

    clean = _CROSS_QUOTED_RE.sub("", formula)
    clean = _CROSS_BARE_RE.sub("", clean)

    for col1, row1, col2, row2 in _RANGE_RE.findall(clean):
        refs.extend(_expand_range(current_sheet, col1, int(row1), col2, int(row2)))

    clean_no_ranges = _RANGE_RE.sub("", clean)
    for col, row in _CELL_RE.findall(clean_no_ranges):
        refs.append((current_sheet, f"{col.lstrip('$').upper()}{row}"))

    return list(set(refs))


def _compute_node_metrics(args: tuple) -> tuple:
    """Compute ancestry/descendant metrics for a single node — runs in thread pool."""
    node, G = args
    ancestor_set   = nx.ancestors(G, node)
    descendant_set = nx.descendants(G, node)
    return node, {
        "out_degree":  G.out_degree(node),
        "in_degree":   G.in_degree(node),
        "is_terminal": G.out_degree(node) == 0,
        "ancestors":   len(ancestor_set),
        "descendants": len(descendant_set),
        "sheet_depth": len({n[0] for n in ancestor_set} - {node[0]}),
    }


def build_graph(cells: list[dict]) -> nx.DiGraph:
    """
    Input:  cell dicts (with formula and sheet/cell fields)
    Output: DiGraph with node metrics; writes raw_dependencies onto each cell dict

    Node metrics computed in parallel across worker threads (65% CPU).
    """
    G: nx.DiGraph = nx.DiGraph()

    # Pass 1 — add nodes and edges
    for cell in cells:
        node = (cell["sheet"], cell["cell"])
        G.add_node(node)
        deps = extract_refs(cell.get("formula") or "", cell["sheet"])
        cell["raw_dependencies"] = deps
        for dep_node in deps:
            G.add_node(dep_node)
            G.add_edge(dep_node, node)

    # Pass 2 — compute node metrics in parallel
    nodes = list(G.nodes())
    workers = min(_MAX_WORKERS, len(nodes))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for node, metrics in pool.map(_compute_node_metrics, [(n, G) for n in nodes]):
            G.nodes[node].update(metrics)

    logger.info("[dependency_graph] Built: %s", {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "terminal": sum(1 for n in G.nodes if G.nodes[n]["is_terminal"]),
    })
    return G


def get_terminal_cells(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """Return whitelisted cells that are terminal (no dependents) in the graph."""
    return [
        c for c in cells
        if G.nodes.get((c["sheet"], c["cell"]), {}).get("is_terminal", False)
    ]
