"""CLI for TimesFM wrapper."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from timesfm_wrapper.adapters.generic import forecast_series
from timesfm_wrapper.timesfm_client import TimesFMClient

app = typer.Typer(help="TimesFM workspace wrapper CLI")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@app.command()
def forecast(
    path: str = typer.Argument(..., help="Path to CSV/JSON/NPY time series file"),
    horizon: int = typer.Option(12, "--horizon", "-h", help="Forecast horizon"),
    column: Optional[str] = typer.Option(None, "--column", "-c", help="Column name for CSV/JSON"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON file"),
):
    """Run a forecast from a file."""
    results = forecast_series(path, horizon=horizon, column=column, output=output)
    out = json.dumps([r.to_dict() for r in results], indent=2)
    print(out)


@app.command()
def health():
    """Check model / CUDA status."""
    client = TimesFMClient.get()
    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False
    print(json.dumps({"model_name": client.model_name, "cuda_available": cuda}, indent=2))


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
):
    """Run FastAPI server."""
    import uvicorn

    uvicorn.run("timesfm_wrapper.api:router", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
