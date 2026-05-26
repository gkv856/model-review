"""
Step 11 — LLM Reviewer
Input:  enriched Tier 1 + Tier 2 representatives, terminal cells for cross-section pass
Output: list[dict] of issues + llm_calls count

Three review passes:
  review_tier1         — full enriched context, batch 20, grouped by sheet+section
  review_tier2         — lightweight (formula + label only), batch 50
  review_cross_section — single call on all terminal output cells

All LLM calls go through get_llm() from llm_provider.py.
Retry once on failure; on second failure, skip batch and log.
"""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from llm_provider import get_llm
from utils import chunked, parse_llm_json

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

TIER1_SYSTEM_PROMPT = """You are a financial model integrity reviewer at a Big 4 accounting firm.

You are reviewing UNIQUE formulas from a financial model. These cells have been
pre-selected as high-risk by a dependency graph analysis — they sit on the critical
path and errors here propagate to many downstream outputs.

Each cell includes: sheet, cell reference, symbol type (F=formula, S=sum, C=callup),
label, units, section, period, formula string, computed value, and full dependency
detail (label + value of each referenced cell).

YOUR ONLY JOB: identify MATHEMATICAL INTEGRITY issues.

Do NOT comment on:
- Naming or labelling conventions
- Whether a value should be a formula (handled separately)
- Formatting or style

Flag issues in these categories only:
INCORRECT_AGGREGATION  - formula sums/subtracts wrong cells for the stated label
SIGN_ERROR             - value should be negative but is positive or vice versa
MISSING_COMPONENT      - subtotal is missing a line item logically expected in section
WRONG_OPERATOR         - multiply where divide is correct or vice versa
UNIT_MISMATCH          - formula mixes cells with incompatible units
SCOPE_ERROR            - references wrong period, section, or sheet for stated label
CALLUP_MISMATCH        - C-type cell references source that does not match its label

Respond ONLY in this JSON format, no preamble:
{"issues": [{"sheet": "...", "cell": "...", "label": "...", "symbol": "...", "issue_type": "...", "severity": "CRITICAL|WARNING|INFO", "description": "...", "suggested_fix": "..."}]}

If no issues: {"issues": []}"""

TIER2_SYSTEM_PROMPT = """You are a financial model integrity reviewer.

You will receive a batch of formula cells with label and formula only.
Flag ONLY obvious mathematical integrity issues — wrong operator, clear sign error,
or aggregation that is structurally wrong for the label.

Do not flag anything you are uncertain about. If the formula looks plausible given
the label, return no issue for that cell. This is a fast pass — only flag
high-confidence issues.

Respond ONLY in this JSON format, no preamble:
{"issues": [{"sheet": "...", "cell": "...", "label": "...", "symbol": "...", "issue_type": "...", "severity": "CRITICAL|WARNING|INFO", "description": "...", "suggested_fix": "..."}]}

If no issues: {"issues": []}"""

CROSS_SECTION_SYSTEM_PROMPT = """You are a financial model integrity reviewer.

You will receive the terminal output cells from each section of a financial model —
the final values that each section produces before feeding the next.

Check for:
- Sign flips between sections (e.g. revenue is positive but feeds as negative into P&L total)
- Unit inconsistencies across section boundaries
- Missing linkage: a section output that should feed the next section but doesn't appear as an input
- Structural gaps: a section that logically follows another but is not connected

Tag all findings as issue_type: CROSS_SECTION_INCONSISTENCY.

Respond ONLY in this JSON format, no preamble:
{"issues": [{"sheet": "...", "cell": "...", "label": "...", "symbol": "...", "issue_type": "CROSS_SECTION_INCONSISTENCY", "severity": "CRITICAL|WARNING|INFO", "description": "...", "suggested_fix": "..."}]}

If no issues: {"issues": []}"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_tier1_user_prompt(cells: list[dict]) -> str:
    items = []
    for c in cells:
        deps = [
            f"  - {d['cell']} ({d['label']}): {d['value']}"
            for d in c.get("dependencies", [])
        ]
        dep_str = "\n".join(deps) if deps else "  (none resolved)"
        items.append(
            f"Sheet: {c['sheet']} | Cell: {c['cell']} | Symbol: {c['symbol']}\n"
            f"Label: {c.get('label', '')} | Units: {c.get('units', '')} | "
            f"Period: {c.get('period', '')} | Section: {c.get('section', '')}\n"
            f"Formula: {c.get('formula', '')} | Value: {c.get('value', '')}\n"
            f"Dependencies:\n{dep_str}"
        )
    return "\n\n---\n\n".join(items)


def _build_tier2_user_prompt(cells: list[dict]) -> str:
    items = [
        f"Sheet: {c['sheet']} | Cell: {c['cell']} | Symbol: {c['symbol']} | "
        f"Label: {c.get('label', '')} | Formula: {c.get('formula', '')}"
        for c in cells
    ]
    return "\n".join(items)


def _build_cross_section_prompt(cells: list[dict]) -> str:
    items = [
        f"Sheet: {c['sheet']} | Cell: {c['cell']} | Section: {c.get('section', '')} | "
        f"Label: {c.get('label', '')} | Value: {c.get('value', '')} | Units: {c.get('units', '')}"
        for c in cells
    ]
    return "\n".join(items)


def _group_by_sheet_section(cells: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for c in cells:
        key = (c["sheet"], c.get("section", "General"))
        groups.setdefault(key, []).append(c)
    return groups


async def _call_llm_with_retry(system_prompt: str, user_prompt: str) -> list[dict]:
    """Single LLM call with one retry on failure. Returns parsed issues list."""
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    for attempt in range(2):
        try:
            response = await llm.ainvoke(messages)
            return parse_llm_json(response.content)
        except Exception as exc:
            if attempt == 0:
                logger.warning("[llm_reviewer] Attempt 1 failed (%s), retrying...", exc)
                await asyncio.sleep(2)
            else:
                logger.error("[llm_reviewer] Batch skipped after 2 failures: %s", exc)
                return []

    return []


# ── public API ────────────────────────────────────────────────────────────────

async def review_tier1(cells: list[dict]) -> tuple[list[dict], int]:
    """
    Input:  enriched Tier 1 representative cells
    Output: (issues, llm_call_count)

    Groups by sheet+section, batches 20 per call.
    """
    if not cells:
        return [], 0

    issues: list[dict] = []
    calls = 0
    groups = _group_by_sheet_section(cells)

    for (sheet, section), group in groups.items():
        for batch in chunked(group, 20):
            user_prompt = _build_tier1_user_prompt(batch)
            batch_issues = await _call_llm_with_retry(TIER1_SYSTEM_PROMPT, user_prompt)
            issues.extend(batch_issues)
            calls += 1

    logger.info("[llm_reviewer] Tier 1 done: %d cells, %d calls, %d issues", len(cells), calls, len(issues))
    return issues, calls


async def review_tier2(cells: list[dict]) -> tuple[list[dict], int]:
    """
    Input:  enriched Tier 2 representative cells
    Output: (issues, llm_call_count)

    Lightweight prompt, batches 50 per call.
    """
    if not cells:
        return [], 0

    issues: list[dict] = []
    calls = 0

    for batch in chunked(cells, 50):
        user_prompt = _build_tier2_user_prompt(batch)
        batch_issues = await _call_llm_with_retry(TIER2_SYSTEM_PROMPT, user_prompt)
        issues.extend(batch_issues)
        calls += 1

    logger.info("[llm_reviewer] Tier 2 done: %d cells, %d calls, %d issues", len(cells), calls, len(issues))
    return issues, calls


async def review_cross_section(terminal_cells: list[dict]) -> tuple[list[dict], int]:
    """
    Input:  terminal output cells (is_terminal=True, from Tier 1+2)
    Output: (issues, llm_call_count)

    Single call reviewing structural consistency between sections.
    Skipped if fewer than 2 terminal cells.
    """
    if len(terminal_cells) < 2:
        return [], 0

    user_prompt = _build_cross_section_prompt(terminal_cells)
    issues = await _call_llm_with_retry(CROSS_SECTION_SYSTEM_PROMPT, user_prompt)
    logger.info("[llm_reviewer] Cross-section done: %d terminal cells, %d issues", len(terminal_cells), len(issues))
    return issues, 1


async def run_llm_review(
    tier1_reps: list[dict],
    tier2_reps: list[dict],
) -> dict:
    """
    Input:  enriched Tier 1 + Tier 2 representative cells
    Output: {"issues": [...], "llm_calls": N}

    Orchestrates all three review passes and combines results.
    """
    t1_issues, t1_calls = await review_tier1(tier1_reps)
    t2_issues, t2_calls = await review_tier2(tier2_reps)

    terminal = [c for c in tier1_reps + tier2_reps if c.get("is_terminal")]
    xs_issues, xs_calls = await review_cross_section(terminal)

    all_issues = t1_issues + t2_issues + xs_issues
    total_calls = t1_calls + t2_calls + xs_calls

    logger.info(
        "[llm_reviewer] Total: %d issues, %d LLM calls",
        len(all_issues), total_calls,
    )
    return {"issues": all_issues, "llm_calls": total_calls}
