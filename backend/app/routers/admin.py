"""Admin endpoints for one-off and recurring scraper runs.

The scrapers use synchronous SQLAlchemy.  To avoid greenlet / async
SQLAlchemy conflicts, the admin run endpoint launches a subprocess that
runs in a clean Python interpreter with no async engine state.  On Render
free tier the pipeline is long-running, so we start it in the background
and return a job id immediately.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])


ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")

# In-memory job tracking (restarts clear this, but stdout is also written to a log file).
_jobs: dict[str, dict] = {}


def _require_secret(secret: str | None):
    if not ADMIN_SECRET:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET not configured")
    if not secret or secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/run-scrapers")
async def run_scrapers(x_admin_secret: str = Header(default="")):
    """Trigger the scraper pipeline in a background subprocess."""
    _require_secret(x_admin_secret)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    # Copy env and force a synchronous SQLite path so the scrapers do not
    # inherit the async app database state.
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{repo_root}/backend"

    # Force scrapers to use the same absolute SQLite DB the app uses.
    db_path = _resolve_shared_db_path(repo_root)
    env["DATABASE_URL_SYNC"] = f"sqlite:///{db_path}"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    job_id = str(uuid.uuid4())[:8]
    log_path = os.path.join(repo_root, "scraper_run", f"run_{job_id}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "scraper.run_all",
        cwd=repo_root,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    _jobs[job_id] = {
        "id": job_id,
        "started_at": datetime.utcnow().isoformat(),
        "pid": proc.pid,
        "returncode": None,
        "log_path": log_path,
        "database_path": db_path,
    }

    asyncio.create_task(_collect_proc(job_id, proc, log_path))

    return {
        "job_id": job_id,
        "status": "started",
        "pid": proc.pid,
        "log_path": log_path,
        "database_path": db_path,
    }


async def _collect_proc(job_id: str, proc: asyncio.subprocess.Process, log_path: str):
    """Collect stdout/stderr from the background scraper process."""
    with open(log_path, "wb") as log:
        async def drain(stream, prefix):
            while True:
                line = await stream.readline()
                if not line:
                    break
                log.write(prefix + line)
                log.flush()
        await asyncio.gather(
            drain(proc.stdout, b"[out] "),
            drain(proc.stderr, b"[err] "),
        )
    await proc.wait()
    _jobs[job_id]["returncode"] = proc.returncode
    _jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()


@router.get("/run-scrapers/{job_id}")
async def get_scraper_run(job_id: str, x_admin_secret: str = Header(default="")):
    """Return the status and tail of a scraper run."""
    _require_secret(x_admin_secret)
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    tail = ""
    try:
        with open(job["log_path"], "rb") as f:
            tail = f.read()[-4000:].decode("utf-8", errors="replace")
    except Exception:
        pass
    return {"job": job, "log_tail": tail}


@router.get("/run-scrapers")
async def list_scraper_runs(x_admin_secret: str = Header(default="")):
    """List all tracked scraper runs."""
    _require_secret(x_admin_secret)
    return {"jobs": list(_jobs.values())}


@router.get("/debug-signal/{signal_type}")
async def debug_signal(signal_type: str, x_admin_secret: str = Header(default="")):
    """Serialize one signal of the given type and return any Pydantic error."""
    _require_secret(x_admin_secret)
    from sqlalchemy import select
    from app.db import async_session_maker
    from app.models import Signal
    from app.schemas import SignalRead
    async with async_session_maker() as db:
        result = await db.execute(select(Signal).where(Signal.signal_type == signal_type).limit(1))
        sig = result.scalar_one_or_none()
        if not sig:
            return {"found": False, "signal_type": signal_type}
        raw = {
            "id": str(sig.id),
            "company_id": str(sig.company_id),
            "signal_type": sig.signal_type.value,
            "severity": sig.severity,
            "headline": sig.headline,
            "summary": sig.summary,
            "source_url": sig.source_url,
            "source_api": sig.source_api,
            "location_name": sig.location_name,
            "detected_at": str(sig.detected_at),
            "published_at": str(sig.published_at),
            "metadata": sig.metadata_,
        }
        try:
            out = SignalRead.model_validate(sig, from_attributes=True).model_dump()
            return {"found": True, "ok": True, "data": out}
        except Exception as e:
            import traceback
            return {"found": True, "ok": False, "error": str(e), "traceback": traceback.format_exc(), "raw": raw}


def _resolve_shared_db_path(repo_root: str) -> str:
    """Return the absolute path used by both app and scrapers for SQLite."""
    backend_dir = os.path.join(repo_root, "backend")
    # If app is currently running in Render, cwd may be backend already.
    if os.path.isfile(os.path.join(backend_dir, "leadsignal.db")):
        return os.path.abspath(os.path.join(backend_dir, "leadsignal.db"))
    # If the env already points somewhere, use that.
    env_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_SYNC")
    if env_url:
        url = env_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        if not url.startswith("/"):
            return os.path.abspath(os.path.join(backend_dir, url))
        return url
    return os.path.abspath(os.path.join(backend_dir, "leadsignal.db"))
