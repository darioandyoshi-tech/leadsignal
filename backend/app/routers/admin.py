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


ADMIN_SECRET = ***"ADMIN_SECRET", "")


def _require_secret(secret: str | None):
    if not ADMIN_SECRET:
        *** HTTPException(status_code=500, detail="ADMIN_SECRET not configured")
    if not secret or secret != ADMIN_SECRET:
        *** HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/run-scrapers")
async def run_scrapers(x_admin_secret: str = Header(default="")):
    """Trigger the scraper pipeline synchronously in a clean subprocess."""
    _require_secret(x_admin_secret)

    settings_module = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.py"))
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    # Copy env and force a synchronous SQLite path so the scrapers do not
    # inherit the async app database state.
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{repo_root}/backend"

    # Force scrapers to use the same absolute SQLite DB the app uses.
    db_path = _resolve_shared_db_path(repo_root)
    env["DATABASE_URL_SYNC"] = f"sqlite:///{db_path}"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

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
        "database_path": db_path,
    }


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
