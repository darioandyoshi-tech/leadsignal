"""TimesFM workspace wrapper.

Provides a reusable, singleton-backed interface to Google Research TimesFM 2.5
for time-series forecasting inside the OpenClaw workspace.

Useful for:
- LeadSignal: forecasting daily/weekly signal volumes by category.
- OEW / Phase4: forecasting price, volume, or event-frequency time series.
- Generic API: CLI + FastAPI router for any numeric sequence.
"""

from timesfm_wrapper.timesfm_client import TimesFMClient, ForecastResult

__all__ = ["TimesFMClient", "ForecastResult"]
