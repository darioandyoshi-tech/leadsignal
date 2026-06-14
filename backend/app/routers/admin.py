"""Admin endpoints for one-off and recurring scraper runs.

The scrapers use synchronous SQLAlchemy.  To avoid greenlet / async
SQLAlchemy conflicts, the admin run endpoint launches a subprocess that
runs in a clean Python interpreter with no async engine state.
"""

import os
import subprocess
import sys
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])


ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def _require_secret(secret: str | None):
    if not ADMIN_SECRET:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET not configured")
    if not secret or secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/run-scrapers")
async def run_scrapers(x_admin_secret: str = Header(default="")):
    """Trigger the scraper pipeline synchronously in a clean subprocess."""
    _require_secret(x_admin_secret)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    # Copy env and force a synchronous SQLite path so the scrapers do not
    # inherit the async app database state.
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{repo_root}/backend"

    # Force scrapers to use the same sync DB the app uses by default.
    db_url = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if db_url and "sqlite+aiosqlite" in db_url:
        db_url = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
    if db_url:
        env["DATABASE_URL_SYNC"] = db_url
        env["DATABASE_URL"] = db_url

    proc = subprocess.run(
        [sys.executable, "-m", "scraper.run_all"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }
