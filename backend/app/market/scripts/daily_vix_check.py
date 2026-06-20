#!/usr/bin/env python3
"""Daily VIX term-structure regime check.

Fetches spot VIX and VIX3M, classifies the current market regime, and
saves the result to ``app/market/data/vix_regime.json``.

Usage::

    venv312/bin/python app/market/scripts/daily_vix_check.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from app.market.vix_regime import VIXRegimeFilter

logger = logging.getLogger("daily_vix_check")

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "vix_regime.json"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Fetching VIX regime data …")

    try:
        vrf = VIXRegimeFilter()
        regime = vrf.get_regime()
    except Exception as exc:
        logger.error("Failed to compute VIX regime: %s", exc, exc_info=True)
        return 1

    # Add a timestamp
    regime["computed_at"] = datetime.now(timezone.utc).isoformat()

    # Ensure data dir exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w") as fh:
        json.dump(regime, fh, indent=2, sort_keys=False)

    logger.info("Saved VIX regime to %s", OUTPUT_PATH)
    logger.info(
        "Regime: %s | VIX %.2f | VIX3M %.2f | spread %.2f%% | pos_mult %.2f | stop_mult %.2f",
        regime["regime"],
        regime["vix_spot"],
        regime["vix_3m"],
        regime["spread_pct"],
        regime["position_multiplier"],
        regime["stop_multiplier"],
    )
    print()
    print(json.dumps(regime, indent=2))
    print()
    print(f"Recommendation: {regime['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())