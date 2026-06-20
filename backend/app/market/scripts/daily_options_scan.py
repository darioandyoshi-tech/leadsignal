#!/usr/bin/env python3
"""Daily options flow signal scan.

Scans top 50 S&P 500 stocks for options flow signals using yfinance
options chain data. Detects unusual options activity, put/call ratios,
and max pain pricing.

Output: app/market/data/options_flow_signals.json
Format: {
    "scan_timestamp": str,
    "signals": [
        {
            "symbol": str,
            "signal": "BULLISH"/"BEARISH"/"NEUTRAL",
            "put_call_volume_ratio": float,
            ...
        }
    ],
    "summary": {"bullish": int, "bearish": int, "neutral": int}
}

Usage:
    python app/market/scripts/daily_options_scan.py [--dry-run] [--symbols AAPL,NVDA,TSLA]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from app.market.options_flow import OptionsFlowScanner, SP500_TOP_50

# Output path
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "options_flow_signals.json"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_options_scan")


def run_scan(symbols: list, dry_run: bool = False) -> dict:
    """Run options flow scan for given symbols.

    Returns the combined output dict.
    """
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting options flow scan for {len(symbols)} symbols...")
    start = time.time()

    scanner = OptionsFlowScanner(rate_limit_sec=0.5, volume_threshold=3.0)
    try:
        signals = scanner.get_batch_flow_signals(symbols)
    finally:
        scanner.close()

    elapsed = time.time() - start

    # Build summary
    bullish = sum(1 for s in signals if s.get("signal") == "BULLISH")
    bearish = sum(1 for s in signals if s.get("signal") == "BEARISH")
    neutral = sum(1 for s in signals if s.get("signal") == "NEUTRAL")
    errors = sum(1 for s in signals if s.get("error"))

    print(f"[Scan] Complete in {elapsed:.1f}s — BULLISH: {bullish}, BEARISH: {bearish}, NEUTRAL: {neutral}, ERRORS: {errors}")

    output = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "symbols_scanned": len(symbols),
        "signals": signals,
        "summary": {
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "errors": errors,
            "total": len(signals),
        },
    }

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily options flow scan")
    parser.add_argument("--dry-run", action="store_true", help="Print results but don't save JSON")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols (default: SP500 top 50)",
    )
    args = parser.parse_args()

    # Determine symbols
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = SP500_TOP_50

    output = run_scan(symbols, dry_run=args.dry_run)

    if args.dry_run:
        print("\n--- DRY RUN RESULTS ---")
        for s in output["signals"]:
            sym = s.get("symbol", "?")
            sig = s.get("signal", "?")
            pcr = s.get("put_call_volume_ratio", "?")
            unusual = s.get("unusual_calls", 0) + s.get("unusual_puts", 0)
            err = s.get("error", "")
            line = f"  {sym:6s} {sig:8s} PCR={pcr:>6} unusual={unusual:>3}"
            if err:
                line += f"  ERROR: {err}"
            print(line)
        print(f"\nSummary: BULLISH={output['summary']['bullish']}, BEARISH={output['summary']['bearish']}, NEUTRAL={output['summary']['neutral']}")
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"[Scan] Results saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()