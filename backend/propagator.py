"""
Step 12 — Result Propagator
Input:  issues list + representative cell dicts (with pattern_instances set)
Output: same issues list with instances/instance_count populated (mutates in place)

When a finding is identified on a representative cell, it applies to every cell
that shares the same structural pattern. instance_count surface this in the report.
"""

import logging

logger = logging.getLogger(__name__)


def propagate_findings(issues: list[dict], representatives: list[dict]) -> list[dict]:
    """
    Input:  issues from LLM/rule checkers, representative cell dicts
    Output: same list with instances and instance_count set on each issue

    Lookup is by (sheet, cell) match. If a match exists and has pattern_instances,
    the full instance list is built as [rep_cell] + pattern_instances.
    If no match, instance list = [issue cell], count = 1.
    """
    rep_index: dict[tuple, dict] = {
        (r["sheet"], r["cell"]): r
        for r in representatives
    }

    propagated = 0
    for issue in issues:
        key = (issue.get("sheet", ""), issue.get("cell", ""))
        rep = rep_index.get(key)

        if rep and rep.get("pattern_instances"):
            instances = [(rep["sheet"], rep["cell"])] + rep["pattern_instances"]
            issue["instances"] = instances
            issue["instance_count"] = len(instances)
            propagated += 1
        else:
            issue["instances"] = [key]
            issue["instance_count"] = 1

    logger.info(
        "[propagator] %d issues propagated to %d+ cells",
        propagated, propagated,
    )
    return issues
