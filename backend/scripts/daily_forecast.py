"""Daily trend forecast cron script for LeadSignal.

Can be scheduled via APScheduler or a separate cron job. It reads signals
from the configured database, runs TimesFM forecasts per category, and writes
a JSON report to stdout or an optional file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add workspace root so timesfm_wrapper is importable if run from backend venv.
workspace_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(workspace_root))

# TimesFM must be imported from its dedicated venv. When this script is run
# via `python run_timesfm.py leadsignal/backend/scripts/daily_forecast.py ...`
# the correct interpreter is already active. Otherwise we warn.
try:
    from timesfm_wrapper.adapters.leadsignal_adapter import LeadSignalForecaster
except ImportError as exc:
    raise ImportError(
        "Run this script through the TimesFM launcher: "
        "python run_timesfm.py leadsignal/backend/scripts/daily_forecast.py"
    ) from exc

# LeadSignal db access
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.models import Signal
from app.config import get_settings


def fetch_signals(sync_db_url: str):
    engine = create_engine(sync_db_url)
    Session = sessionmaker(engine)
    with Session() as session:
        rows = session.execute(select(Signal)).scalars().all()
        return [
            {
                "signal_type": r.signal_type.value,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            }
            for r in rows
        ]


def main():
    parser = argparse.ArgumentParser(description="LeadSignal daily trend forecast")
    parser.add_argument("--horizon", type=int, default=7, help="Forecast horizon in days")
    parser.add_argument("--bucket-days", type=int, default=1)
    parser.add_argument("--output", type=str, default=None, help="Optional JSON output file")
    args = parser.parse_args()

    settings = get_settings()
    records = fetch_signals(settings.sync_database_url)

    forecaster = LeadSignalForecaster()
    forecasts = forecaster.forecast_all(records, horizon_days=args.horizon, bucket_days=args.bucket_days)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "horizon_days": args.horizon,
        "bucket_days": args.bucket_days,
        "total_signals": len(records),
        "forecasts": {k: v.to_dict() for k, v in forecasts.items()},
    }

    out = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(out)
    print(out)


if __name__ == "__main__":
    main()
