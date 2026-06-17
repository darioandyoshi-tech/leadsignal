"""Standalone TimesFM forecast microservice.

Runs a FastAPI app inside the timesfm venv. The model is loaded once at startup
and kept resident for fast warm inference.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from timesfm_wrapper.timesfm_client import TimesFMClient


class ForecastRequest(BaseModel):
    series: List[float]
    horizon: int = Field(..., ge=1, le=256)
    return_quantiles: bool = True


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
    inference_ms: float


class CategoryForecastRequest(BaseModel):
    records: List[Dict[str, Any]]
    horizon_days: int = Field(7, ge=1, le=30)
    bucket_days: int = Field(1, ge=1, le=7)


client: Optional[TimesFMClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    print("Loading TimesFM model...")
    start = time.time()
    client = TimesFMClient.get()
    # Warm-up inference to force compilation / cache.
    client.forecast_single([1.0, 2.0, 3.0, 4.0, 5.0], horizon=3)
    print(f"Model ready in {time.time() - start:.2f}s")
    yield
    client = None


app = FastAPI(title="TimesFM Forecast Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": client is not None,
        "model_name": client.model_name if client else None,
    }


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    if client is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    start = time.time()
    result = client.forecast_single(req.series, horizon=req.horizon)
    return ForecastResponse(
        point=result.point.tolist(),
        quantiles=result.quantiles.tolist() if req.return_quantiles else None,
        horizon=result.horizon,
        input_length=result.input_length,
        model_name=result.model_name,
        inference_ms=(time.time() - start) * 1000,
    )


@app.post("/forecast/batch", response_model=List[ForecastResponse])
def forecast_batch(req: BatchForecastRequest):
    if client is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    start = time.time()
    results = client.forecast(req.series_list, horizon=req.horizon)
    ms = (time.time() - start) * 1000
    return [
        ForecastResponse(
            point=r.point.tolist(),
            quantiles=r.quantiles.tolist() if req.return_quantiles else None,
            horizon=r.horizon,
            input_length=r.input_length,
            model_name=r.model_name,
            inference_ms=ms / len(results),
        )
        for r in results
    ]


@app.post("/forecast/signal-trends")
def signal_trends(req: CategoryForecastRequest):
    """LeadSignal-specific: forecast daily signal volume per category."""
    if client is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    from timesfm_wrapper.adapters.leadsignal_adapter import LeadSignalForecaster

    start = time.time()
    forecaster = LeadSignalForecaster(client=client)
    forecasts = forecaster.forecast_all(
        req.records, horizon_days=req.horizon_days, bucket_days=req.bucket_days
    )
    out = {k: v.to_dict() for k, v in forecasts.items()}
    out["_inference_ms"] = (time.time() - start) * 1000
    return out
