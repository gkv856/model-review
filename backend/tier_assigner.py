"""
Step 5 — Tier Assigner
Input:  scored cell dicts (risk_score on each F/S/C cell)
Output: same cells with tier (1 | 2 | 3) added; N/X cells get tier="AUTO"

Thresholds are percentile-based (dynamic) so tier sizes stay proportional
regardless of model size. Falls back to fixed thresholds if all scores identical.

Tier 1 = top (100 - TIER1_PERCENTILE)% by score — critical path, full LLM review
Tier 2 = between TIER2_PERCENTILE and TIER1_PERCENTILE — lightweight LLM review
Tier 3 = bottom TIER2_PERCENTILE% — rule-based checks only, no LLM
"""

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

_TIER1_PCT = int(os.getenv("TIER1_PERCENTILE", "85"))
_TIER2_PCT = int(os.getenv("TIER2_PERCENTILE", "50"))

# Fixed fallback thresholds used when all scores are identical
_FALLBACK_TIER1 = 60.0
_FALLBACK_TIER2 = 30.0


def assign_tiers(cells: list[dict]) -> list[dict]:
    """
    Input:  cell dicts with risk_score set on F/S/C cells
    Output: same list with tier field added (mutates in place)
    """
    scored = [c for c in cells if c["symbol"] in ("F", "S", "C")]

    # N and X cells are always AUTO-flagged, no tier assignment
    for cell in cells:
        if cell["symbol"] in ("N", "X"):
            cell["tier"] = "AUTO"

    if not scored:
        return cells

    scores    = [c["risk_score"] for c in scored]
    score_arr = np.array(scores)

    # Detect flat distribution (all identical) → use fallback thresholds
    if score_arr.std() < 1e-6:
        t1_threshold = _FALLBACK_TIER1
        t2_threshold = _FALLBACK_TIER2
        logger.warning("[tier_assigner] All scores identical — using fallback thresholds")
    else:
        t1_threshold = float(np.percentile(score_arr, _TIER1_PCT))
        t2_threshold = float(np.percentile(score_arr, _TIER2_PCT))

    for cell in scored:
        score = cell["risk_score"]
        if score >= t1_threshold:
            cell["tier"] = 1
        elif score >= t2_threshold:
            cell["tier"] = 2
        else:
            cell["tier"] = 3

    tier_counts = {1: 0, 2: 0, 3: 0}
    for cell in scored:
        tier_counts[cell["tier"]] = tier_counts.get(cell["tier"], 0) + 1

    log_data = {
        "tier1_threshold": round(t1_threshold, 2),
        "tier2_threshold": round(t2_threshold, 2),
        "tier_counts":     tier_counts,
    }
    logger.info("[tier_assigner] Tiers assigned: %s", log_data)

    return cells
