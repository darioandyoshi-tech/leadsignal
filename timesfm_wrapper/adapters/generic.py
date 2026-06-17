"""Generic adapter: read series from CSV/JSON and write forecasts back."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from timesfm_wrapper.timesfm_client import ForecastResult, TimesFMClient


def _load_series(path: str, column: Optional[str] = None) -> List[np.ndarray]:
    p = Path(path)
    if p.suffix == ".csv":
        import pandas as pd

        df = pd.read_csv(path)
        if column:
            return [df[column].dropna().to_numpy(dtype=float)]
        # If no column, try first numeric column
        numeric = df.select_dtypes(include=[np.number])
        if numeric.empty:
            raise ValueError("No numeric columns found in CSV")
        return [numeric.iloc[:, 0].dropna().to_numpy(dtype=float)]
    elif p.suffix == ".json":
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict) and column:
            return [np.asarray(data[column], dtype=float)]
        if isinstance(data, list):
            return [np.asarray(data, dtype=float)]
        raise ValueError("JSON must be an array or an object with a numeric column")
    elif p.suffix in (".npy", ".npz"):
        arr = np.load(path)
        if isinstance(arr, np.ndarray):
            return [arr.astype(float)]
        raise ValueError("Unsupported .npz structure")
    else:
        raise ValueError(f"Unsupported file extension: {p.suffix}")


def forecast_series(
    path: str,
    horizon: int,
    column: Optional[str] = None,
    output: Optional[str] = None,
) -> List[ForecastResult]:
    """Load a time series from `path` and forecast `horizon` steps ahead.

    Args:
        path: CSV/JSON/NPY file path.
        horizon: forecast steps.
        column: optional column name for CSV/JSON objects.
        output: optional path to write JSON results.

    Returns:
        List of ForecastResult.
    """
    client = TimesFMClient.get()
    series_list = _load_series(path, column)
    results = client.forecast(series_list, horizon)
    if output:
        Path(output).write_text(
            json.dumps([r.to_dict() for r in results], indent=2)
        )
    return results
