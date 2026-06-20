#!/usr/bin/env python3
"""Daily cointegrated pairs scan.

Finds cointegrated pairs among the top 100 S&P 500 stocks, generates
current trading signals, and saves results to
``app/market/data/pairs_signals.json``.

Usage::

    venv312/bin/python app/market/scripts/daily_pairs_scan.py [--limit N]

Options:
    --limit N      Number of top S&P 500 symbols to scan (default 100)
    --test         Quick test mode: scan 20 symbols only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from app.market.statarb_pairs import PairsTrader, get_sp500_top_symbols

logger = logging.getLogger("daily_pairs_scan")

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "pairs_signals.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily pairs trading scan")
    parser.add_argument("--limit", type=int, default=100,
                        help="Number of S&P 500 symbols to scan (default 100)")
    parser.add_argument("--test", action="store_true",
                        help="Quick test mode: scan 20 symbols")
    parser.add_argument("--max-pairs", type=int, default=500,
                        help="Max pairs to test (default 500)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    n_symbols = 20 if args.test else args.limit
    symbols = get_sp500_top_symbols(n_symbols)

    logger.info("Scanning %d S&P 500 symbols for cointegrated pairs …", len(symbols))

    pt = PairsTrader()

    # Find cointegrated pairs
    try:
        pairs = pt.find_cointegrated_pairs(
            symbols,
            lookback_days=252,
            max_pairs=args.max_pairs,
        )
    except Exception as exc:
        logger.error("Failed to find pairs: %s", exc, exc_info=True)
        return 1

    logger.info("Found %d cointegrated pairs", len(pairs))

    if not pairs:
        logger.warning("No cointegrated pairs found — saving empty result")

    # Generate current signals
    try:
        signals = pt.get_pair_signals(pairs)
    except Exception as exc:
        logger.error("Failed to generate signals: %s", exc, exc_info=True)
        signals = []

    logger.info("Generated %d signals", len(signals))

    # Log notable signals
    enter_signals = [s for s in signals if s["signal"].startswith("ENTER")]
    stop_signals = [s for s in signals if s["signal"] == "STOP"]
    exit_signals = [s for s in signals if s["signal"] == "EXIT"]

    for s in enter_signals:
        logger.info("  ENTER: %s/%s z=%.2f", s["symbol_a"], s["symbol_b"], s["z_score"])
    for s in stop_signals:
        logger.warning("  STOP:  %s/%s z=%.2f", s["symbol_a"], s["symbol_b"], s["z_score"])

    # Build output
    output = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(symbols),
        "symbols_scanned": symbols,
        "num_cointegrated_pairs": len(pairs),
        "pairs": pairs,
        "signals": signals,
        "summary": {
            "enter_signals": len(enter_signals),
            "exit_signals": len(exit_signals),
            "stop_signals": len(stop_signals),
            "hold_signals": len([s for s in signals if s["signal"] == "HOLD"]),
        },
    }

    # Ensure data dir exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, sort_keys=False)

    logger.info("Saved pairs signals to %s", OUTPUT_PATH)
    print()
    print(json.dumps(output["summary"], indent=2))
    print()
    if enter_signals:
        print("=== ENTRY SIGNALS ===")
        for s in enter_signals:
            print(f"  {s['symbol_a']}/{s['symbol_b']}  z={s['z_score']}  "
                  f"signal={s['signal']}  hedge={s['hedge_ratio']}")
    if stop_signals:
        print("=== STOP SIGNALS ===")
        for s in stop_signals:
            print(f"  {s['symbol_a']}/{s['symbol_b']}  z={s['z_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())