"""
Step 6 — Auto Flagger
Input:  all cell dicts (with tier assigned) + built DiGraph
Output: list[dict] of issues for N/X cells and graph-level errors

Detects:
  1. X-in-chain  — an X (excluded) cell is depended on by an F/S/C cell
  2. Circular ref — networkx detects cycles in the DiGraph
  3. Broken ref   — formula references a coord not present in the model file
"""

import networkx as nx

from utils.helpers import make_issue
from utils.logger import get_logger

logger = get_logger(__name__)


def flag_x_in_chain(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Return issues for F/S/C cells that depend (directly) on X cells.
    An X cell that feeds into the computation chain is suspicious because
    it was explicitly excluded from the model map yet is still referenced.
    """
    x_nodes = {
        (c["sheet"], c["cell"])
        for c in cells
        if c["symbol"] == "X"
    }
    if not x_nodes:
        return []

    issues = []
    for cell in cells:
        if cell["symbol"] not in ("F", "S", "C"):
            continue
        node = (cell["sheet"], cell["cell"])
        deps = set(G.predecessors(node)) if node in G else set()
        x_deps = deps & x_nodes
        if x_deps:
            issues.append(make_issue(
                sheet=cell["sheet"],
                cell=cell["cell"],
                label=cell.get("label", ""),
                symbol=cell["symbol"],
                tier=cell.get("tier", "AUTO"),
                issue_type="x_in_chain",
                severity="WARNING",
                description=(
                    f"Cell references excluded (X) cell(s): "
                    f"{', '.join(str(n) for n in sorted(x_deps))}. "
                    "Excluded cells may contain intentionally omitted logic."
                ),
                suggested_fix="Review whether the excluded cell should be included in the model map.",
            ))
    return issues


def flag_circular_refs(G: nx.DiGraph) -> list[dict]:
    """Return one issue per cycle detected in the dependency graph."""
    issues = []
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        return issues

    for cycle in cycles:
        nodes_str = " → ".join(f"{s}!{c}" for s, c in cycle)
        sheet, cell = cycle[0]
        issues.append(make_issue(
            sheet=sheet,
            cell=cell,
            symbol="F",
            tier=1,
            issue_type="circular_ref",
            severity="CRITICAL",
            description=f"Circular dependency detected: {nodes_str}",
            suggested_fix="Break the cycle by restructuring the formula chain.",
        ))
    return issues


def flag_broken_refs(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Return issues for cells whose raw_dependencies reference coordinates
    not present in the whitelist. build_graph adds phantom nodes for all
    referenced coords so we compare against the explicit cells list, not G.nodes().
    """
    known_nodes = {(c["sheet"], c["cell"]) for c in cells}
    issues = []

    for cell in cells:
        if cell["symbol"] not in ("F", "S", "C"):
            continue
        missing = [
            dep for dep in cell.get("raw_dependencies", [])
            if dep not in known_nodes
        ]
        if missing:
            issues.append(make_issue(
                sheet=cell["sheet"],
                cell=cell["cell"],
                label=cell.get("label", ""),
                symbol=cell["symbol"],
                tier=cell.get("tier", "AUTO"),
                issue_type="broken_ref",
                severity="WARNING",
                description=(
                    f"Formula references cell(s) not found in the model: "
                    f"{', '.join(str(m) for m in sorted(missing))}."
                ),
                suggested_fix="Verify the referenced cells exist and are correctly named.",
            ))
    return issues


def auto_flag(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    """
    Run all automatic flaggers and return the combined issue list.
    """
    x_issues     = flag_x_in_chain(cells, G)
    circ_issues  = flag_circular_refs(G)
    broken_issues = flag_broken_refs(cells, G)

    issues = x_issues + circ_issues + broken_issues

    logger.info(
        "[auto_flagger] x_in_chain=%d circular=%d broken_ref=%d",
        len(x_issues), len(circ_issues), len(broken_issues),
    )
    return issues
