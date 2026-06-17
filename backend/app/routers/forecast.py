"""Trend forecasting endpoint powered by TimesFM.

This router adds a `/forecast/signal-trends` route to LeadSignal that forecasts
future daily signal volumes by category. It uses the workspace TimesFM wrapper
(`timesfm_wrapper`) which lives in the repository root.

The wrapper runs in a dedicated venv (`/workspace/timesfm/venv`) because
TimesFM + PyTorch have heavy compiled dependencies. For production Render/Fly
deployments the easiest path is:

- Run the TimesFM wrapper as a separate microservice, or
- Add the same venv setup to the deployment image.

For local dev this endpoint works as long as `python run_timesfm.py ...` style
launcher can be invoked from the backend directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_optional
from app.models import Signal, SignalType, User

router = APIRouter(prefix="/forecast", tags=["forecast"])


class TrendForecastResponse(BaseModel):
    category: str
    horizon_days: int
    history_length: int
    point_forecast: List[float]
    quantiles: Optional[List[List[float]]] = None
    model_name: str = "google/timesfm-2.5-200m-pytorch"
    error: Optional[str] = None


@router.get("/signal-trends", response_model=List[TrendForecastResponse])
async def signal_trends(
    horizon_days: int = Query(7, ge=1, le=30),
    bucket_days: int = Query(1, ge=1, le=7),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Forecast future signal volume per category over the next N days."""
    # Pull all signals (MVP: public read)
    result = await db.execute(select(Signal))
    rows = result.scalars().all()

    records = [
        {
            "signal_type": r.signal_type.value,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]

    # Delegate to the workspace TimesFM wrapper.
    # Prefer a resident microservice if TIMESFM_URL is set; otherwise fall back
    # to spawning the wrapper subprocess (slower cold-start).
    workspace_root = Path(__file__).resolve().parents[4]
    timesfm_url = os.environ.get("TIMESFM_URL")

    try:
        if timesfm_url:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{timesfm_url}/forecast/signal-trends",
                    json={
                        "records": records,
                        "horizon_days": horizon_days,
                        "bucket_days": bucket_days,
                    },
                )
                if resp.status_code >= 400:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"TimesFM service error: {resp.text[:500]}",
                    )
                raw = resp.json()
        else:
            launcher = workspace_root / "run_timesfm.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(launcher),
                    "-c",
                    "import json,sys; "
                    "from timesfm_wrapper.adapters.leadsignal_adapter import LeadSignalForecaster; "
                    f"rec=json.load(sys.stdin); "
                    f"f=LeadSignalForecaster(); "
                    f"out={{k:v.to_dict() for k,v in f.forecast_all(rec, horizon_days={horizon_days}, bucket_days={bucket_days}).items()}}; "
                    "print(json.dumps(out))",
                ],
                input=json.dumps(records),
                capture_output=True,
                text=True,
                cwd=str(workspace_root),
                timeout=300,
                check=False,
            )
            if proc.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"TimesFM subprocess failed: {proc.stderr[:500]}",
                )
            raw = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TimesFM forecast timed out")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"TimesFM launcher not found: {exc}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid TimesFM output: {exc}. stdout={proc.stdout[:500] if 'proc' in locals() else ''}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"TimesFM service unreachable: {exc}")

    responses = []
    for category, payload in raw.items():
        if category.startswith("_"):
            continue
        responses.append(
            TrendForecastResponse(
                category=category,
                horizon_days=horizon_days,
                history_length=payload.get("input_length", 0),
                point_forecast=payload.get("point", []),
                quantiles=payload.get("quantiles"),
                model_name=payload.get("model_name", "google/timesfm-2.5-200m-pytorch"),
            )
        )
    return responses
