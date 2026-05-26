"""
In-memory job store. A single module-level dict shared across the process.

Job schema:
  status:   "pending" | "running" | "completed" | "failed"
  progress: 0-100
  step:     current step label string
  error:    str | None
  report:   dict | None
"""

JOB_STORE: dict[str, dict] = {}


def create_job(job_id: str) -> dict:
    """Initialise a new job entry and return it."""
    job = {
        "status":   "pending",
        "progress": 0,
        "step":     "queued",
        "error":    None,
        "report":   None,
    }
    JOB_STORE[job_id] = job
    return job


def get_job(job_id: str) -> dict | None:
    return JOB_STORE.get(job_id)


def update_progress(job_id: str, progress: int, step: str) -> None:
    job = JOB_STORE.get(job_id)
    if job:
        job["progress"] = progress
        job["step"]     = step
