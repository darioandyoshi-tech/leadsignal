"""Example: forecast incident/event rate for OEW-style data."""

import json
from datetime import datetime, timedelta
from timesfm_wrapper.adapters.oew_adapter import OEWForecaster

if __name__ == "__main__":
    now = datetime.utcnow()
    # Simulate event timestamps clustering around business hours
    timestamps = [
        now - timedelta(minutes=i * 7 + (i % 3) * 2)
        for i in range(500)
    ]

    forecaster = OEWForecaster()
    result = forecaster.forecast_event_rate(timestamps, bucket_minutes=60, horizon_buckets=12)
    print(json.dumps(result.to_dict(), indent=2))
