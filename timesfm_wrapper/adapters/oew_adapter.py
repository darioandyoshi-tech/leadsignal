"""OEW / Phase4 adapter: forecast numeric market/event series."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from timesfm_wrapper.timesfm_client import ForecastResult, TimesFMClient


class OEWForecaster:
    """Forecaster for OEW-style numeric sequences: prices, volumes, event counts."""

    def __init__(self, client: Optional[TimesFMClient] = None):
        self.client = client or TimesFMClient.get()

    @staticmethod
    def _to_series(values: List[float | int]) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if arr.ndim != 1:
            raise ValueError("Input series must be 1-D")
        return arr

    def forecast_price(
        self,
        prices: List[float],
        horizon: int = 12,
    ) -> ForecastResult:
        """Forecast next price steps from a close-price series."""
        return self.client.forecast_single(self._to_series(prices), horizon=horizon)

    def forecast_volume(
        self,
        volumes: List[float],
        horizon: int = 12,
    ) -> ForecastResult:
        """Forecast next volume steps."""
        return self.client.forecast_single(self._to_series(volumes), horizon=horizon)

    def forecast_event_rate(
        self,
        timestamps: List[datetime | str | float],
        bucket_minutes: int = 60,
        horizon_buckets: int = 12,
    ) -> ForecastResult:
        """Aggregate event timestamps into buckets and forecast future event rate."""
        from collections import defaultdict

        bucket_counts = defaultdict(int)
        for ts in timestamps:
            if isinstance(ts, datetime):
                dt = ts
            elif isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = datetime.utcfromtimestamp(ts)
            # Bucket start
            minute_bucket = (dt.hour * 60 + dt.minute) // bucket_minutes
            key = dt.replace(minute=0, second=0, microsecond=0)
            key = key.replace(hour=0) + timedelta(minutes=minute_bucket * bucket_minutes)
            bucket_counts[key] += 1

        if not bucket_counts:
            series = np.zeros(1, dtype=float)
        else:
            start = min(bucket_counts)
            end = max(bucket_counts)
            n_buckets = int((end - start).total_seconds() // (bucket_minutes * 60)) + 1
            series = np.zeros(n_buckets, dtype=float)
            for b, c in bucket_counts.items():
                idx = int((b - start).total_seconds() // (bucket_minutes * 60))
                series[idx] = c
        return self.client.forecast_single(series, horizon=horizon_buckets)


# Convenience function for use in cron/heartbeat scripts.
def forecast_market_series(
    series_name: str,
    values: List[float],
    horizon: int = 12,
) -> Dict[str, Any]:
    """Named wrapper returning a plain dict."""
    client = TimesFMClient.get()
    result = client.forecast_single(values, horizon=horizon)
    return {
        "series": series_name,
        "horizon": horizon,
        "forecast": result.to_dict(),
    }
