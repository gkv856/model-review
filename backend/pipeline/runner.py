"""
Pipeline Runner — orchestrates all 13 steps end-to-end.

Called from api/routes.py as a background task. Progress is written to
the job store via a callback so routes can serve status updates.
"""

import asyncio
from typing import Callable

import openpyxl

from analysis.auto_flagger import auto_flag
from analysis.deduplicator import deduplicate_by_pattern
from analysis.enricher import enrich_cells
from analysis.tier3_checker import run_tier3_checks
from core.dependency_graph import build_graph
from core.map_parser import parse_map, symbol_counts
from core.model_parser import parse_model
from core.risk_scorer import score_cells
from core.structure_detector import detect_structure
from core.tier_assigner import assign_tiers
from llm.reviewer import run_llm_review
from pipeline import interim
from reporting.generator import build_html_report, build_json_report
from reporting.propagator import propagate_findings
from utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(
    job_id: str,
    model_path: str,
    map_path: str,
    model_filename: str,
    map_filename: str,
    update_progress: Callable[[int, str], None],
) -> dict:
    """
    Input:  file paths, filenames, progress callback
    Output: completed JSON report dict

    Raises on failure — caller is responsible for catching and marking job failed.
    Progress callback: update_progress(percent: int, step_label: str)
    """

    # Step 0 — Map parser
    update_progress(5, "Parsing map file")
    whitelist   = parse_map(map_path)
    sym_counts  = symbol_counts(whitelist)
    interim.write_map_parsed(job_id, whitelist)

    # Step 1 — Model parser
    update_progress(10, "Parsing model file")
    cells = parse_model(model_path, whitelist)
    interim.write_cells_parsed(job_id, cells)

    # Step 2 — Structure detection
    update_progress(20, "Detecting model structure")
    wb_formulas   = openpyxl.load_workbook(model_path, data_only=False)
    wb_values     = openpyxl.load_workbook(model_path, data_only=True)
    structure_map = detect_structure(wb_formulas)
    interim.write_structure_map(job_id, structure_map)

    # Step 3 — Build dependency graph
    update_progress(30, "Building dependency graph")
    G = build_graph(cells)
    interim.write_graph_metrics(job_id, G)

    # Step 4 — Risk scoring
    update_progress(40, "Scoring cells")
    score_cells(cells, G)
    interim.write_cells_scored(job_id, cells)

    # Step 5 — Tier assignment
    update_progress(45, "Assigning tiers")
    assign_tiers(cells)
    interim.write_cells_tiered(job_id, cells)

    # Step 6 — Auto-flagging
    update_progress(50, "Auto-flagging N/X cells and graph errors")
    auto_issues = auto_flag(cells, G)
    interim.write_auto_flags(job_id, auto_issues)

    # Step 7 — Tier 3 rule checks
    update_progress(55, "Running Tier 3 rule checks")
    tier3_issues = run_tier3_checks(cells, G)
    interim.write_tier3_issues(job_id, tier3_issues)

    # Step 8 — Deduplication (Tier 1 + 2 only)
    update_progress(60, "Deduplicating formula patterns")
    tier1_reps = deduplicate_by_pattern([c for c in cells if c.get("tier") == 1])
    tier2_reps = deduplicate_by_pattern([c for c in cells if c.get("tier") == 2])
    all_reps   = tier1_reps + tier2_reps
    patterns_reviewed = len(all_reps)
    interim.write_deduplication(job_id, tier1_reps, tier2_reps)

    # Step 9 — Enrichment
    update_progress(65, "Enriching representative cells")
    enrich_cells(all_reps, structure_map, wb_values)
    interim.write_cells_enriched(job_id, all_reps)

    # Step 10 — LLM review
    update_progress(70, "Running LLM review (this may take a few minutes)")
    llm_result = asyncio.run(run_llm_review(tier1_reps, tier2_reps))
    llm_issues = llm_result["issues"]
    llm_calls  = llm_result["llm_calls"]
    interim.write_llm_issues(job_id, llm_issues)
    interim.write_llm_prompts(job_id, llm_result.get("prompts", []))

    # Step 11 — Propagation
    update_progress(90, "Propagating findings")
    propagate_findings(llm_issues, all_reps)
    propagate_findings(tier3_issues, all_reps)
    all_rule_issues = tier3_issues
    interim.write_propagated_issues(job_id, llm_issues + all_rule_issues + auto_issues)

    # Step 12 — Report generation
    update_progress(95, "Generating report")
    report = build_json_report(
        job_id=job_id,
        model_filename=model_filename,
        map_filename=map_filename,
        cells=cells,
        issues=llm_issues + all_rule_issues,
        auto_issues=auto_issues,
        llm_calls_made=llm_calls,
        patterns_reviewed=patterns_reviewed,
    )

    logger.info("[runner] Job %s complete — %d issues", job_id, report["summary"]["total_issues"])
    return report
