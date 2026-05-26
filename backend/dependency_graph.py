"""
Step 3 — Dependency Graph Builder
Input:  list of cell dicts from parser
Output: networkx DiGraph + raw_dependencies stored on each cell dict

Edge direction: dependency → dependent
  A1 feeds C1  →  edge (Sheet1, A1) → (Sheet1, C1)

Node metrics stored on graph nodes:
  out_degree, in_degree, is_terminal, sheet_depth, ancestors, descendants
"""

import logging
import re

import networkx as nx
from openpyxl.utils import column_index_from_string, get_column_letter

logger = logging.getLogger(__name__)

MAX_RANGE_CELLS = 200   # cap range expansion to avoid memory blow-up

# ── reference extraction ─────────────────────────────────────────────────────

# Quoted cross-sheet: 'Sheet Name'!A1  or  'P&L'!B5
_CROSS_QUOTED_RE = re.compile(r"'([^']+)'!\$?([A-Z]+)\$?(\d+)", re.IGNORECASE)
# Bare cross-sheet: SheetName!A1  (no spaces, no ampersand in name)
_CROSS_BARE_RE   = re.compile(r"(?<!['])([A-Za-z0-9_]+)!\$?([A-Z]+)\$?(\d+)", re.IGNORECASE)
# Range same-sheet: A1:B10  (must not be preceded by !)
_RANGE_RE        = re.compile(r"(?<!!)(\$?[A-Z]+)\$?(\d+):(\$?[A-Z]+)\$?(\d+)", re.IGNORECASE)
# Single cell same-sheet: A1  (not preceded by ! or letter—avoids function names)
_CELL_RE         = re.compile(r"(?<![!A-Za-z])(\$?[A-Z]+)\$?(\d+)(?![A-Za-z])")


def _expand_range(sheet: str, col1: str, row1: int, col2: str, row2: int) -> list[tuple[str, str]]:
    """Expand a range reference into individual (sheet, coord) tuples, capped at MAX_RANGE_CELLS."""
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

    # 1. Quoted cross-sheet refs
    for sheet, col, row in _CROSS_QUOTED_RE.findall(formula):
        refs.append((sheet, f"{col.upper()}{row}"))

    # 2. Bare cross-sheet refs
    for sheet, col, row in _CROSS_BARE_RE.findall(formula):
        refs.append((sheet, f"{col.upper()}{row}"))

    # Remove cross-sheet refs from formula so single-cell RE doesn't double-count
    clean = _CROSS_QUOTED_RE.sub("", formula)
    clean = _CROSS_BARE_RE.sub("", clean)

    # 3. Range expansion (same sheet)
    for col1, row1, col2, row2 in _RANGE_RE.findall(clean):
        refs.extend(_expand_range(current_sheet, col1, int(row1), col2, int(row2)))

    # Remove ranges before extracting single cells
    clean_no_ranges = _RANGE_RE.sub("", clean)

    # 4. Single same-sheet cell refs
    for col, row in _CELL_RE.findall(clean_no_ranges):
        refs.append((current_sheet, f"{col.lstrip('$').upper()}{row}"))

    return list(set(refs))


# ── graph builder ─────────────────────────────────────────────────────────────

def _count_ancestor_sheets(G: nx.DiGraph, node: tuple) -> int:
    """Return number of distinct sheets in node's ancestors."""
    ancestors = nx.ancestors(G, node) if node in G else set()
    return len({n[0] for n in ancestors} - {node[0]})


def build_graph(cells: list[dict]) -> nx.DiGraph:
    """
    Input:  cell dicts (with formula and sheet/cell fields)
    Output: DiGraph with node metrics; also writes raw_dependencies onto each cell dict

    Node metrics added to G.nodes[node]:
      out_degree, in_degree, is_terminal, sheet_depth, ancestors, descendants
    """
    G: nx.DiGraph = nx.DiGraph()

    # Pass 1 — add all whitelisted nodes and extract dependencies
    for cell in cells:
        node = (cell["sheet"], cell["cell"])
        G.add_node(node)

        deps = extract_refs(cell.get("formula") or "", cell["sheet"])
        cell["raw_dependencies"] = deps

        for dep_node in deps:
            G.add_node(dep_node)
            G.add_edge(dep_node, node)   # dep feeds this cell

    # Pass 2 — compute and store per-node metrics
    for node in list(G.nodes()):
        ancestor_set  = nx.ancestors(G, node)
        descendant_set = nx.descendants(G, node)

        G.nodes[node]["out_degree"]  = G.out_degree(node)
        G.nodes[node]["in_degree"]   = G.in_degree(node)
        G.nodes[node]["is_terminal"] = G.out_degree(node) == 0
        G.nodes[node]["ancestors"]   = len(ancestor_set)
        G.nodes[node]["descendants"] = len(descendant_set)
        G.nodes[node]["sheet_depth"] = len({n[0] for n in ancestor_set} - {node[0]})

    log_data = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "terminal_nodes": sum(1 for n in G.nodes if G.nodes[n]["is_terminal"]),
    }
    logger.info("[dependency_graph] Graph built: %s", log_data)

    return G


def get_terminal_cells(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """Return whitelisted cells that are terminal (no dependents) in the graph."""
    return [
        c for c in cells
        if G.nodes.get((c["sheet"], c["cell"]), {}).get("is_terminal", False)
    ]
