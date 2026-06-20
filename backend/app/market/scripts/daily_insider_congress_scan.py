#!/usr/bin/env python3
"""Daily insider + congressional trading signal scan.

Fetches recent SEC Form 4 insider transactions and congressional trading
data, generates signals, and writes the combined output to JSON.

Output: app/market/data/insider_congress_signals.json
Format: {"insider_signals": [...], "congressional_signals": [...]}

Usage:
    python app/market/scripts/daily_insider_congress_scan.py [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from app.market.insider_trades import InsiderTradeScanner
from app.market.congressional_trades import CongressionalTradeScanner

# Output path
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "insider_congress_signals.json"


def run_insider_scan() -> list:
    """Run the SEC Form 4 insider trading scanner."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting insider trade scan...")
    start = time.time()

    scanner = InsiderTradeScanner(fetch_count=100, max_pages=3)
    try:
        signals = scanner.get_insider_signals()
    finally:
        scanner.close()

    elapsed = time.time() - start
    print(f"[Insider] Found {len(signals)} signals in {elapsed:.1f}s")
    return signals


def run_congressional_scan() -> list:
    """Run the congressional trading scanner."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting congressional trade scan...")
    start = time.time()

    scanner = CongressionalTradeScanner()
    try:
        signals = scanner.get_congressional_signals()
    finally:
        scanner.close()

    elapsed = time.time() - start
    print(f"[Congress] Found {len(signals)} signals in {elapsed:.1f}s")
    return signals


def main(dry_run: bool = False) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Daily insider + congressional scan starting...")
    if dry_run:
        print("[Scan] DRY RUN — results will be printed but not saved to JSON")

    # Run scans
    insider_signals = run_insider_scan()
    congressional_signals = run_congressional_scan()

    # Combine results
    output = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "insider_signals": insider_signals,
        "congressional_signals": congressional_signals,
    }

    # Print summary
    print("\n" + "=" * 70)
    print("SCAN SUMMARY")
    print("=" * 70)

    # Insider signals
    print(f"\n--- Insider Signals ({len(insider_signals)}) ---")
    for s in insider_signals:
        insiders_str = ", ".join(s.get("insiders", [])[:3])
        print(
            f"  {s['symbol']:6s}  {s['signal']:12s}  "
            f"cluster={s['cluster_count']}  "
            f"date={s['last_transaction_date']}  "
            f"insiders=[{insiders_str}...]"
        )

    # Congressional signals
    print(f"\n--- Congressional Signals ({len(congressional_signals)}) ---")
    for s in congressional_signals:
        print(
            f"  {s['symbol']:6s}  {s['signal']:12s}  "
            f"politician={s['politician']}  "
            f"committee={s['committee']}  "
            f"date={s['transaction_date']}  "
            f"cluster={s['cluster_count']}"
        )

    print("\n" + "=" * 70)

    if dry_run:
        print("[Scan] DRY RUN — not writing output file")
        return

    # Write output
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[Scan] Output written to {OUTPUT_PATH}")
    print(f"[Scan] Done at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Daily insider + congressional trading signal scan."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print results but don't save JSON file",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)