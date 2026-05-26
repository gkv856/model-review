"""
FastAPI route handlers.
Routes: POST /review, GET /status/{job_id}, GET /report/{job_id}, GET /report/{job_id}/html
"""

import os
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from api.job_store import JOB_STORE, create_job, get_job, update_progress
from pipeline.runner import run_pipeline
from reporting.generator import build_html_report
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024


# ── Background task ───────────────────────────────────────────────────────────

def _background_pipeline(
    job_id: str,
    model_path: str,
    map_path: str,
    model_filename: str,
    map_filename: str,
) -> None:
    job = JOB_STORE[job_id]
    job["status"] = "running"

    def _update(progress: int, step: str) -> None:
        update_progress(job_id, progress, step)
        logger.info("[routes] Job %s — %d%% — %s", job_id, progress, step)

    try:
        report = run_pipeline(
            job_id=job_id,
            model_path=model_path,
            map_path=map_path,
            model_filename=model_filename,
            map_filename=map_filename,
            update_progress=_update,
        )
        job["report"]   = report
        job["status"]   = "completed"
        job["progress"] = 100
        job["step"]     = "completed"
        logger.info("[routes] Job %s completed", job_id)

    except Exception as exc:
        job["status"] = "failed"
        job["error"]  = str(exc)
        logger.error("[routes] Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())

    finally:
        try:
            from pathlib import Path
            shutil.rmtree(Path(model_path).parent, ignore_errors=True)
        except Exception:
            pass


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
async def root():
    return {
        "status":  "running",
        "service": "Financial Model Integrity Reviewer",
        "version": "2.0.0",
        "endpoints": {
            "POST /review":               "Upload model.xlsx + map.xlsx to start a review job",
            "GET  /status/{job_id}":      "Poll job progress (status, progress %, current step)",
            "GET  /report/{job_id}":      "Fetch full JSON report (job must be completed)",
            "GET  /report/{job_id}/html": "Fetch standalone HTML report (job must be completed)",
            "GET  /health":               "Health check",
        },
    }


@router.post("/review")
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

    tmp_dir    = tempfile.mkdtemp()
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
    create_job(job_id)

    background_tasks.add_task(
        _background_pipeline,
        job_id, model_path, map_path,
        model_file.filename, map_file.filename,
    )
    logger.info("[routes] Submitted job %s", job_id)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Return current job status, progress percentage, current step, and any error."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    return {
        "job_id":   job_id,
        "status":   job["status"],
        "progress": job["progress"],
        "step":     job["step"],
        "error":    job["error"],
    }


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    """Return the full JSON report for a completed job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, detail=f"Job not completed (status: {job['status']})")
    return JSONResponse(content=job["report"])


@router.get("/report/{job_id}/html", response_class=HTMLResponse)
async def get_report_html(job_id: str):
    """Return the standalone HTML report for a completed job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, detail=f"Job not completed (status: {job['status']})")
    html = build_html_report(job["report"])
    return HTMLResponse(content=html)


@router.get("/interim/{job_id}")
async def list_interim_files(job_id: str):
    """List all interim stage files available for a job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    interim_dir = Path("interim") / job_id
    if not interim_dir.exists():
        return {"job_id": job_id, "files": []}
    files = sorted(
        {"name": f.name, "size_bytes": f.stat().st_size}
        for f in interim_dir.iterdir()
        if f.is_file()
    )
    return {"job_id": job_id, "files": files}


@router.get("/interim/{job_id}/{filename}")
async def download_interim_file(job_id: str, filename: str):
    """Download a single interim stage file by name."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, detail="Invalid filename")
    file_path = Path("interim") / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, detail="File not found")
    media_type = "application/json" if filename.endswith(".json") else "text/csv"
    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@router.get("/health")
async def health():
    return {"status": "ok"}
