"""
Step 14 — FastAPI Application
Routes: POST /review, GET /status/{job_id}, GET /report/{job_id}, GET /report/{job_id}/html

Pipeline runs as a FastAPI BackgroundTask, writing progress to an in-memory JOB_STORE.
Uploaded files are saved to a temp directory and cleaned up after the pipeline finishes.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path

import openpyxl
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from auto_flagger import auto_flag
from dependency_graph import build_graph, get_terminal_cells
from deduplicator import deduplicate_by_pattern
from enricher import enrich_cells
from llm_reviewer import run_llm_review
from map_parser import parse_map, symbol_counts
from parser import parse_model
from propagator import propagate_findings
from report_generator import build_html_report, build_json_report
from risk_scorer import score_cells
from structure_detector import detect_structure
from tier_assigner import assign_tiers
from tier3_checker import run_tier3_checks

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Job store ─────────────────────────────────────────────────────────────────

JOB_STORE: dict[str, dict] = {}

# ── App setup ─────────────────────────────────────────────────────────────────

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="Financial Model Integrity Reviewer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _update(job_id: str, progress: int, step: str) -> None:
    JOB_STORE[job_id]["progress"] = progress
    JOB_STORE[job_id]["step"] = step
    logger.info("[main] Job %s — %d%% — %s", job_id, progress, step)


def _run_pipeline(job_id: str, model_path: str, map_path: str,
                  model_filename: str, map_filename: str) -> None:
    """Synchronous pipeline; runs in FastAPI BackgroundTask thread."""
    job = JOB_STORE[job_id]
    job["status"] = "running"

    try:
        # Step 0 — Map parser
        _update(job_id, 5, "Parsing map file")
        whitelist = parse_map(map_path)
        sym_counts = symbol_counts(whitelist)

        # Step 1 — Model parser
        _update(job_id, 10, "Parsing model file")
        cells = parse_model(model_path, whitelist)

        # Step 2 — Structure detection
        _update(job_id, 20, "Detecting model structure")
        wb_formulas  = openpyxl.load_workbook(model_path, data_only=False)
        wb_values    = openpyxl.load_workbook(model_path, data_only=True)
        structure_map = detect_structure(wb_formulas)

        # Step 3 — Build dependency graph
        _update(job_id, 30, "Building dependency graph")
        G = build_graph(cells)

        # Step 4 — Risk scoring
        _update(job_id, 40, "Scoring cells")
        score_cells(cells, G)

        # Step 5 — Tier assignment
        _update(job_id, 45, "Assigning tiers")
        assign_tiers(cells)

        # Step 6 — Auto-flagging
        _update(job_id, 50, "Auto-flagging N/X cells and graph errors")
        auto_issues = auto_flag(cells, G)

        # Step 7 — Tier 3 rule checks
        _update(job_id, 55, "Running Tier 3 rule checks")
        tier3_issues = run_tier3_checks(cells, G)

        # Step 8 — Deduplication (Tier 1 + 2 only)
        _update(job_id, 60, "Deduplicating formula patterns")
        t1_t2 = [c for c in cells if c.get("tier") in (1, 2)]
        tier1_reps = deduplicate_by_pattern([c for c in t1_t2 if c.get("tier") == 1])
        tier2_reps = deduplicate_by_pattern([c for c in t1_t2 if c.get("tier") == 2])
        all_reps   = tier1_reps + tier2_reps
        patterns_reviewed = len(all_reps)

        # Step 9 — Enrichment
        _update(job_id, 65, "Enriching representative cells")
        enrich_cells(all_reps, structure_map, wb_values)

        # Step 10 — LLM review
        _update(job_id, 70, "Running LLM review (this may take a few minutes)")
        llm_result = asyncio.run(run_llm_review(tier1_reps, tier2_reps))
        llm_issues = llm_result["issues"]
        llm_calls  = llm_result["llm_calls"]

        # Step 11 — Propagation
        _update(job_id, 90, "Propagating findings")
        propagate_findings(llm_issues, all_reps)
        propagate_findings(tier3_issues, all_reps)

        # Step 12 — Report generation
        _update(job_id, 95, "Generating report")
        all_rule_issues = tier3_issues
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

        job["report"]   = report
        job["status"]   = "completed"
        job["progress"] = 100
        job["step"]     = "completed"
        logger.info("[main] Job %s completed", job_id)

    except Exception as exc:
        job["status"] = "failed"
        job["error"]  = str(exc)
        logger.error("[main] Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())

    finally:
        # Clean up temp files
        try:
            shutil.rmtree(Path(model_path).parent, ignore_errors=True)
        except Exception:
            pass


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/review")
async def submit_review(
    background_tasks: BackgroundTasks,
    model_file: UploadFile = File(...),
    map_file:   UploadFile = File(...),
):
    """
    Accept multipart upload of model + map Excel files.
    Validates file types and size, then kicks off the background pipeline.
    Returns {job_id}.
    """
    for f in (model_file, map_file):
        if not (f.filename or "").lower().endswith(".xlsx"):
            raise HTTPException(400, detail=f"File must be .xlsx: {f.filename}")

    tmp_dir = tempfile.mkdtemp()
    model_path = os.path.join(tmp_dir, "model.xlsx")
    map_path   = os.path.join(tmp_dir, "map.xlsx")

    for upload, dest in ((model_file, model_path), (map_file, map_path)):
        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(413, detail=f"File too large: {upload.filename}")
        with open(dest, "wb") as fh:
            fh.write(content)

    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {
        "status":   "pending",
        "progress": 0,
        "step":     "queued",
        "error":    None,
        "report":   None,
    }

    background_tasks.add_task(
        _run_pipeline,
        job_id, model_path, map_path,
        model_file.filename, map_file.filename,
    )
    logger.info("[main] Submitted job %s", job_id)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Return current job status, progress percentage, current step, and any error."""
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    return {
        "job_id":   job_id,
        "status":   job["status"],
        "progress": job["progress"],
        "step":     job["step"],
        "error":    job["error"],
    }


@app.get("/report/{job_id}")
async def get_report(job_id: str):
    """Return the full JSON report for a completed job."""
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, detail=f"Job not completed (status: {job['status']})")
    return JSONResponse(content=job["report"])


@app.get("/report/{job_id}/html", response_class=HTMLResponse)
async def get_report_html(job_id: str):
    """Return the standalone HTML report for a completed job."""
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, detail=f"Job not completed (status: {job['status']})")
    html = build_html_report(job["report"])
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    return {"status": "ok"}
