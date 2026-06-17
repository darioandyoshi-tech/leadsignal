"""FastAPI router for TimesFM forecasts.

Usage:
    from fastapi import FastAPI
    from timesfm_wrapper.api import router as timesfm_router

    app = FastAPI()
    app.include_router(timesfm_router)
"""

from __future__ import annotations

from typing import Any, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from timesfm_wrapper.timesfm_client import TimesFMClient

router = APIRouter(prefix="/timesfm", tags=["timesfm"])


class ForecastRequest(BaseModel):
    series: List[float]
    horizon: int = Field(..., ge=1, le=256, description="Number of future steps to predict")
    return_quantiles: bool = True
    metadata: Optional[dict] = None


class BatchForecastRequest(BaseModel):
    series_list: List[List[float]]
    horizon: int = Field(..., ge=1, le=256)
    return_quantiles: bool = True


class ForecastResponse(BaseModel):
    point: List[float]
    quantiles: Optional[List[List[float]]] = None
    horizon: int
    input_length: int
    model_name: str
    metadata: Optional[dict] = None


@router.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest):
    """Forecast a single time series."""
    try:
        client = TimesFMClient.get()
        result = client.forecast_single(req.series, horizon=req.horizon)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ForecastResponse(
        point=result.point.tolist(),
        quantiles=result.quantiles.tolist() if req.return_quantiles else None,
        horizon=result.horizon,
        input_length=result.input_length,
        model_name=result.model_name,
        metadata=req.metadata,
    )


@router.post("/forecast/batch", response_model=List[ForecastResponse])
async def forecast_batch(req: BatchForecastRequest):
    """Forecast multiple time series in one call."""
    try:
        client = TimesFMClient.get()
        results = client.forecast(req.series_list, horizon=req.horizon)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [
        ForecastResponse(
            point=r.point.tolist(),
            quantiles=r.quantiles.tolist() if req.return_quantiles else None,
            horizon=r.horizon,
            input_length=r.input_length,
            model_name=r.model_name,
        )
        for r in results
    ]


@router.get("/health")
async def health():
    """Return whether the model is loaded and CUDA is available."""
    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False
    return {"status": "ok", "cuda_available": cuda}
