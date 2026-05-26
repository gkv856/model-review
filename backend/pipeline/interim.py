"""
Interim file writer — dumps pipeline stage outputs to disk for inspection.

Each stage produces a human-readable CSV or JSON file in:
  outputs/interim/{job_id}/NN_stage_name.{csv|json}

All writes are best-effort: errors are logged but never crash the pipeline.
"""

import csv
import json
from pathlib import Path

import networkx as nx

from utils.logger import get_logger

logger = get_logger(__name__)

# Anchored to backend root so the path is stable regardless of cwd
_BACKEND_ROOT = Path(__file__).parent.parent
_INTERIM_ROOT = _BACKEND_ROOT / "outputs" / "interim"


def _stage_path(job_id: str, filename: str) -> Path:
    d = _INTERIM_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d / filename


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        logger.info("[interim] Written: %s (%d rows)", path, len(rows))
    except Exception as exc:
        logger.warning("[interim] Failed to write %s: %s", path, exc)


def _write_json(path: Path, data) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("[interim] Written: %s", path)
    except Exception as exc:
        logger.warning("[interim] Failed to write %s: %s", path, exc)


# ── Stage writers ─────────────────────────────────────────────────────────────

def write_metadata(job_id: str, model_filename: str, map_filename: str) -> None:
    """00 — Job metadata written at submission time, before the pipeline starts."""
    from datetime import datetime, timezone
    data = {
        "job_id":         job_id,
        "model_filename": model_filename,
        "map_filename":   map_filename,
        "started_at":     datetime.now(timezone.utc).isoformat(),
    }
    _write_json(_stage_path(job_id, "00_meta.json"), data)


def write_map_parsed(job_id: str, whitelist: dict[str, dict[str, str]]) -> None:
    """01 — Flattened whitelist: sheet, cell, symbol."""
    rows = [
        {"sheet": sheet, "cell": coord, "symbol": sym}
        for sheet, cells in whitelist.items()
        for coord, sym in cells.items()
    ]
    _write_csv(_stage_path(job_id, "01_map_parsed.csv"), rows, ["sheet", "cell", "symbol"])


def write_cells_parsed(job_id: str, cells: list[dict]) -> None:
    """02 — All cells from model_parser."""
    _write_csv(
        _stage_path(job_id, "02_cells_parsed.csv"), cells,
        ["sheet", "cell", "row", "col", "symbol", "formula", "value", "is_formula"],
    )


def write_structure_map(job_id: str, structure_map: dict) -> None:
    """03 — Structure map per sheet (JSON)."""
    _write_json(_stage_path(job_id, "03_structure_map.json"), structure_map)


def write_graph_metrics(job_id: str, G: nx.DiGraph) -> None:
    """04 — Node metrics from the dependency graph."""
    rows = []
    for node in G.nodes():
        attrs = G.nodes[node]
        rows.append({
            "sheet":       node[0],
            "cell":        node[1],
            "out_degree":  attrs.get("out_degree", ""),
            "in_degree":   attrs.get("in_degree", ""),
            "is_terminal": attrs.get("is_terminal", ""),
            "ancestors":   attrs.get("ancestors", ""),
            "descendants": attrs.get("descendants", ""),
            "sheet_depth": attrs.get("sheet_depth", ""),
        })
    _write_csv(
        _stage_path(job_id, "04_graph_metrics.csv"), rows,
        ["sheet", "cell", "out_degree", "in_degree", "is_terminal", "ancestors", "descendants", "sheet_depth"],
    )


def write_cells_scored(job_id: str, cells: list[dict]) -> None:
    """05 — Cells with risk_score."""
    scored = [c for c in cells if "risk_score" in c]
    _write_csv(
        _stage_path(job_id, "05_cells_scored.csv"), scored,
        ["sheet", "cell", "symbol", "risk_score"],
    )


def write_cells_tiered(job_id: str, cells: list[dict]) -> None:
    """06 — Cells with tier assignment."""
    _write_csv(
        _stage_path(job_id, "06_cells_tiered.csv"), cells,
        ["sheet", "cell", "symbol", "risk_score", "tier"],
    )


def write_auto_flags(job_id: str, issues: list[dict]) -> None:
    """07 — Auto-flagger issues."""
    _write_csv(
        _stage_path(job_id, "07_auto_flags.csv"), issues,
        ["sheet", "cell", "symbol", "tier", "issue_type", "severity", "description"],
    )


def write_tier3_issues(job_id: str, issues: list[dict]) -> None:
    """08 — Tier 3 rule-check issues."""
    _write_csv(
        _stage_path(job_id, "08_tier3_issues.csv"), issues,
        ["sheet", "cell", "symbol", "tier", "issue_type", "severity", "description"],
    )


def write_deduplication(job_id: str, tier1_reps: list[dict], tier2_reps: list[dict]) -> None:
    """09 — Deduplicated representatives with pattern instance counts."""
    rows = []
    for rep in tier1_reps + tier2_reps:
        rows.append({
            "sheet":                  rep["sheet"],
            "cell":                   rep["cell"],
            "symbol":                 rep["symbol"],
            "tier":                   rep.get("tier", ""),
            "risk_score":             rep.get("risk_score", ""),
            "pattern_instance_count": rep.get("pattern_instance_count", 1),
            "formula":                (rep.get("formula") or "")[:120],
        })
    _write_csv(
        _stage_path(job_id, "09_deduplication.csv"), rows,
        ["sheet", "cell", "symbol", "tier", "risk_score", "pattern_instance_count", "formula"],
    )


def write_cells_enriched(job_id: str, cells: list[dict]) -> None:
    """10 — Enriched representatives."""
    rows = []
    for c in cells:
        rows.append({
            "sheet":   c["sheet"],
            "cell":    c["cell"],
            "symbol":  c["symbol"],
            "tier":    c.get("tier", ""),
            "label":   c.get("label", ""),
            "units":   c.get("units", ""),
            "period":  c.get("period", ""),
            "section": c.get("section", ""),
            "formula": (c.get("formula") or "")[:120],
            "value":   c.get("value", ""),
        })
    _write_csv(
        _stage_path(job_id, "10_cells_enriched.csv"), rows,
        ["sheet", "cell", "symbol", "tier", "label", "units", "period", "section", "formula", "value"],
    )


def write_llm_prompts(job_id: str, prompts: list[dict]) -> None:
    """11p — One record per LLM batch call: pass name, cell refs, full system + user prompt."""
    _write_json(_stage_path(job_id, "11_llm_prompts.json"), prompts)


def write_llm_issues(job_id: str, issues: list[dict]) -> None:
    """11 — Raw LLM issues before propagation."""
    _write_csv(
        _stage_path(job_id, "11_llm_issues.csv"), issues,
        ["sheet", "cell", "label", "symbol", "tier", "issue_type", "severity", "description", "suggested_fix"],
    )


def write_propagated_issues(job_id: str, issues: list[dict]) -> None:
    """12 — All issues after propagation (with instance_count)."""
    rows = []
    for i in issues:
        rows.append({
            "sheet":          i.get("sheet", ""),
            "cell":           i.get("cell", ""),
            "label":          i.get("label", ""),
            "symbol":         i.get("symbol", ""),
            "tier":           i.get("tier", ""),
            "issue_type":     i.get("issue_type", ""),
            "severity":       i.get("severity", ""),
            "instance_count": i.get("instance_count", 1),
            "description":    i.get("description", ""),
            "suggested_fix":  i.get("suggested_fix", ""),
        })
    _write_csv(
        _stage_path(job_id, "12_propagated_issues.csv"), rows,
        ["sheet", "cell", "label", "symbol", "tier", "issue_type", "severity", "instance_count", "description", "suggested_fix"],
    )
