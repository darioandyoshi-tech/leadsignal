"""Admin endpoints for one-off and recurring scraper runs."""

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
    """Trigger the scraper pipeline synchronously."""
    _require_secret(x_admin_secret)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{repo_root}/backend"
    proc = subprocess.run(
        [sys.executable, "-m", "scraper.run_all"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
    }
