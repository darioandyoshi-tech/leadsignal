"""TimesFM adapter for OEW / Phase4 market and incident time series.

Usage:
    from phase4_ssm_leap.integrations.timesfm_oew_adapter import OEWTrendForecaster
    forecaster = OEWTrendForecaster()
    result = forecaster.forecast_incident_rate(timestamps, bucket_minutes=60, horizon=12)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from timesfm_wrapper.adapters.oew_adapter import OEWForecaster


class OEWTrendForecaster:
    """Higher-level wrapper for OEW-specific forecasting tasks."""

    def __init__(self, client: Optional[Any] = None):
        self.forecaster = OEWForecaster(client=client)

    def forecast_incident_rate(
        self,
        timestamps: List[datetime | str | float],
        bucket_minutes: int = 60,
        horizon: int = 12,
    ) -> Dict[str, Any]:
        """Forecast number of incidents per bucket over the next N buckets."""
        result = self.forecaster.forecast_event_rate(
            timestamps,
            bucket_minutes=bucket_minutes,
            horizon_buckets=horizon,
        )
        return {
            "task": "incident_rate_forecast",
            "bucket_minutes": bucket_minutes,
            "horizon": horizon,
            "forecast": result.to_dict(),
        }

    def forecast_price_trend(
        self,
        prices: List[float],
        horizon: int = 12,
    ) -> Dict[str, Any]:
        """Forecast next price steps from a close-price series."""
        result = self.forecaster.forecast_price(prices, horizon=horizon)
        return {
            "task": "price_trend_forecast",
            "horizon": horizon,
            "forecast": result.to_dict(),
        }

    def forecast_volume_trend(
        self,
        volumes: List[float],
        horizon: int = 12,
    ) -> Dict[str, Any]:
        """Forecast next volume steps."""
        result = self.forecaster.forecast_volume(volumes, horizon=horizon)
        return {
            "task": "volume_trend_forecast",
            "horizon": horizon,
            "forecast": result.to_dict(),
        }
