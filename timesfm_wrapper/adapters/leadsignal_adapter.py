"""LeadSignal adapter: forecast signal volumes by category over time."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

from timesfm_wrapper.timesfm_client import ForecastResult, TimesFMClient


class LeadSignalForecaster:
    """Forecasts future signal volumes per SignalType from a list of Signal rows."""

    def __init__(self, client: Optional[TimesFMClient] = None):
        self.client = client or TimesFMClient.get()

    def aggregate_daily(
        self,
        records: List[dict],
        signal_type: Optional[str] = None,
        date_field: str = "detected_at",
        bucket_days: int = 1,
    ) -> Dict[str, np.ndarray]:
        """Aggregate signal counts into daily (or multi-day) buckets.

        Args:
            records: list of signal dicts with at least a date field.
            signal_type: if provided, filter to this signal type.
            date_field: key containing the datetime string/value.
            bucket_days: group into buckets of N days (default 1).

        Returns:
            Dict mapping signal_type -> count array (oldest -> newest).
        """
        buckets = defaultdict(lambda: defaultdict(int))
        for r in records:
            st = r.get("signal_type", "unknown")
            if signal_type and st != signal_type:
                continue
            raw = r.get(date_field)
            if raw is None:
                continue
            if isinstance(raw, datetime):
                dt = raw
            elif isinstance(raw, str):
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                dt = datetime.utcfromtimestamp(raw)
            bucket = dt.date() - timedelta(days=dt.day % bucket_days)
            buckets[st][bucket] += 1

        result = {}
        for st, counts in buckets.items():
            if not counts:
                continue
            start = min(counts)
            end = max(counts)
            days = (end - start).days + 1
            arr = np.zeros(days, dtype=float)
            for d, c in counts.items():
                idx = (d - start).days
                arr[idx] = c
            result[st] = arr
        return result

    def forecast_category(
        self,
        records: List[dict],
        signal_type: str,
        horizon_days: int = 7,
        bucket_days: int = 1,
    ) -> ForecastResult:
        """Forecast future counts for a single signal category."""
        daily = self.aggregate_daily(records, signal_type=signal_type, bucket_days=bucket_days)
        series = daily.get(signal_type, np.zeros(1, dtype=float))
        if len(series) == 0:
            series = np.zeros(1, dtype=float)
        return self.client.forecast_single(series, horizon=horizon_days)

    def forecast_all(
        self,
        records: List[dict],
        horizon_days: int = 7,
        bucket_days: int = 1,
    ) -> Dict[str, ForecastResult]:
        """Forecast future counts for every signal category."""
        daily = self.aggregate_daily(records, bucket_days=bucket_days)
        return {
            st: self.client.forecast_single(series, horizon=horizon_days)
            for st, series in daily.items()
        }
