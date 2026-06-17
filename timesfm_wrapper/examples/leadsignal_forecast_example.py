"""Example: forecast LeadSignal category volumes from a list of signal dicts."""

import json
from datetime import datetime, timedelta
from timesfm_wrapper.adapters.leadsignal_adapter import LeadSignalForecaster

if __name__ == "__main__":
    # Build fake signal stream
    now = datetime.utcnow()
    records = []
    for i in range(120):
        records.append({
            "signal_type": "business_license",
            "detected_at": (now - timedelta(days=i)).isoformat(),
        })
    for i in range(60):
        records.append({
            "signal_type": "permit_filing",
            "detected_at": (now - timedelta(days=i * 2)).isoformat(),
        })

    forecaster = LeadSignalForecaster()
    forecasts = forecaster.forecast_all(records, horizon_days=7)
    out = {k: v.to_dict() for k, v in forecasts.items()}
    print(json.dumps(out, indent=2))
