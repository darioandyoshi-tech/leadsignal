#!/usr/bin/env python3
"""Daily earnings NLP & PEAD signal scan.

Checks S&P 500 stocks for recent earnings reports, fetches transcripts
when available, runs FinBERT Q&A sentiment analysis, and generates PEAD
(Post-Earnings Announcement Drift) signals.

Produces ``app/market/data/earnings_signals.json``:

    {
      "signals": [ { ... } ],
      "upcoming_earnings": [ { ... } ],
      "_meta": { ... }
    }

Usage::

    venv312/bin/python app/market/scripts/daily_earnings_scan.py
    venv312/bin/python app/market/scripts/daily_earnings_scan.py --limit 20   # quick test
    venv312/bin/python app/market/scripts/daily_earnings_scan.py --no-transcripts  # EPS only
"""

from __future__ import annotations

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

from app.market.earnings_nlp import EarningsNLPScanner, SP500_TOP_TICKERS

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "earnings_signals.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_earnings_scan")


def run_scan(
    limit: int = 100,
    lookback_days: int = 5,
    fetch_transcripts: bool = True,
    check_upcoming: bool = True,
    upcoming_days: int = 7,
) -> dict:
    """Run the daily earnings NLP scan.

    Parameters
    ----------
    limit : int
        Number of S&P 500 tickers to scan for recent earnings.
    lookback_days : int
        Days to look back for earnings reports (PEAD entry window).
    fetch_transcripts : bool
        Whether to fetch earnings call transcripts from Motley Fool.
    check_upcoming : bool
        Whether to also scan for upcoming earnings (to avoid pre-earnings risk).
    upcoming_days : int
        How many days ahead to check for upcoming earnings.

    Returns
    -------
    dict
        { "signals": [...], "upcoming_earnings": [...], "_meta": {...} }
    """
    scanner = EarningsNLPScanner(fetch_transcripts=fetch_transcripts)
    symbols = SP500_TOP_TICKERS[:limit]

    logger.info("Scanning %d symbols for recent earnings (lookback %d days) ...", len(symbols), lookback_days)
    signals = scanner.get_earnings_signals(symbols, lookback_days=lookback_days)

    # Sort by confidence descending
    signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    upcoming = []
    if check_upcoming:
        logger.info("Checking upcoming earnings for next %d days ...", upcoming_days)
        try:
            upcoming = scanner.get_upcoming_earnings(days_ahead=upcoming_days)
        except Exception as exc:
            logger.error("Failed to fetch upcoming earnings: %s", exc)

    # Summary
    buy_signals = [s for s in signals if s["signal"] == "BUY"]
    avoid_signals = [s for s in signals if s["signal"] == "AVOID"]
    neutral_signals = [s for s in signals if s["signal"] == "NEUTRAL"]

    logger.info(
        "Earnings signals: %d BUY, %d AVOID, %d NEUTRAL (total: %d)",
        len(buy_signals),
        len(avoid_signals),
        len(neutral_signals),
        len(signals),
    )
    if buy_signals:
        logger.info("  BUY signals:")
        for s in buy_signals:
            logger.info(
                "    %s: conf=%.2f, surprise=%s%%, %s",
                s["symbol"],
                s["confidence"],
                s.get("surprise_pct"),
                s["reasoning"],
            )
    if avoid_signals:
        logger.info("  AVOID signals:")
        for s in avoid_signals:
            logger.info(
                "    %s: conf=%.2f, surprise=%s%%, %s",
                s["symbol"],
                s["confidence"],
                s.get("surprise_pct"),
                s["reasoning"],
            )

    if upcoming:
        logger.info("Upcoming earnings (%d stocks in next %d days):", len(upcoming), upcoming_days)
        for u in upcoming:
            logger.info("  %s: %s (%d days)", u["symbol"], u["earnings_date"], u["days_until"])

    return {
        "signals": signals,
        "upcoming_earnings": upcoming,
        "_meta": {
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "symbols_scanned": len(symbols),
            "lookback_days": lookback_days,
            "transcripts_fetched": fetch_transcripts,
            "model": "ProsusAI/finbert",
            "strategy": "PEAD",
            "summary": {
                "buy": len(buy_signals),
                "avoid": len(avoid_signals),
                "neutral": len(neutral_signals),
                "total_signals": len(signals),
                "upcoming_count": len(upcoming),
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Daily earnings NLP & PEAD scan")
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Number of top S&P 500 stocks to scan (default 100)",
    )
    parser.add_argument(
        "--lookback", type=int, default=5,
        help="Days to look back for earnings reports (default 5)",
    )
    parser.add_argument(
        "--no-transcripts", action="store_true",
        help="Skip transcript fetching (use EPS surprise only)",
    )
    parser.add_argument(
        "--no-upcoming", action="store_true",
        help="Skip upcoming earnings check",
    )
    parser.add_argument(
        "--upcoming-days", type=int, default=7,
        help="Days ahead to check for upcoming earnings (default 7)",
    )
    parser.add_argument(
        "--output", type=str, default=str(OUTPUT_PATH),
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    logger.info("Starting daily earnings NLP scan")
    start = time.time()

    results = run_scan(
        limit=args.limit,
        lookback_days=args.lookback,
        fetch_transcripts=not args.no_transcripts,
        check_upcoming=not args.no_upcoming,
        upcoming_days=args.upcoming_days,
    )

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    elapsed = time.time() - start
    logger.info("Earnings scan complete in %.1fs. Output: %s", elapsed, output_path)


if __name__ == "__main__":
    main()