"""
Step 8 — Formula Pattern Deduplicator
Input:  Tier 1 + Tier 2 cell dicts
Output: one representative per unique structural pattern

normalise_formula() strips cell addresses, ranges, cross-sheet refs, and numeric
constants, leaving only the structural skeleton (operators, function names).

deduplicate_by_pattern() groups by (symbol, pattern), picks the highest
risk_score cell as representative, and stores all other group members in
representative["pattern_instances"].
"""

import re
from collections import defaultdict

from utils.logger import get_logger

logger = get_logger(__name__)

# Cross-sheet refs: 'Sheet Name'!A1  or  SheetName!A1
_XSHEET_QUOTED_RE = re.compile(r"'[^']+'!\$?[A-Z]+\$?\d+", re.IGNORECASE)
_XSHEET_BARE_RE   = re.compile(r"[A-Za-z0-9_]+!\$?[A-Z]+\$?\d+", re.IGNORECASE)
# Ranges: A1:B5
_RANGE_RE         = re.compile(r"\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+", re.IGNORECASE)
# Single cell refs: A1, $A$1
_CELL_RE          = re.compile(r"\$?[A-Z]+\$?\d+", re.IGNORECASE)
# Numeric constants
_CONST_RE         = re.compile(r"\b\d+(?:\.\d+)?\b")


def normalise_formula(formula: str) -> str:
    """
    Input:  raw formula string
    Output: structural pattern with addresses/constants replaced by tokens

    Substitution order: cross-sheet first, then ranges, then single cells,
    then constants — avoids double-matching coordinates inside cross-sheet refs.
    """
    if not formula:
        return ""

    f = formula.upper()
    f = _XSHEET_QUOTED_RE.sub("XSHEET!REF", f)
    f = _XSHEET_BARE_RE.sub("XSHEET!REF", f)
    f = _RANGE_RE.sub("RANGE", f)
    f = _CELL_RE.sub("REF", f)
    f = _CONST_RE.sub("CONST", f)
    return f


def deduplicate_by_pattern(cells: list[dict]) -> list[dict]:
    """
    Input:  list of cell dicts (Tier 1 or Tier 2)
    Output: one representative per (symbol, normalised_pattern) group

    The representative is the cell with the highest risk_score.
    Sets on representative:
      pattern_instances      — (sheet, cell) tuples of non-representative group members
      pattern_instance_count — total group size (including representative)
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)

    for cell in cells:
        pattern = normalise_formula(cell.get("formula") or "")
        key = (cell["symbol"], pattern)
        groups[key].append(cell)

    representatives: list[dict] = []
    total_cells = 0
    total_groups = 0

    for _key, group in groups.items():
        total_cells  += len(group)
        total_groups += 1

        rep    = max(group, key=lambda c: c.get("risk_score", 0.0))
        others = [c for c in group if c is not rep]

        rep["pattern_instances"]      = [(c["sheet"], c["cell"]) for c in others]
        rep["pattern_instance_count"] = len(group)
        representatives.append(rep)

    reduction = round(100 * (1 - total_groups / total_cells), 1) if total_cells else 0
    logger.info(
        "[deduplicator] %d cells → %d patterns (%.1f%% reduction)",
        total_cells, total_groups, reduction,
    )
    return representatives
