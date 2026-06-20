#!/usr/bin/env python3
"""Daily sentiment scan: fetch headlines for top S&P 500 stocks and run FinBERT.

Produces ``app/market/data/daily_sentiment.json`` with the format::

    {
      "AAPL": {
        "sentiment": "positive",
        "score": 0.85,
        "headlines_analyzed": 5,
        "breakdown": {"positive": 3, "negative": 0, "neutral": 2}
      },
      ...
    }

This file is read by the daily market scan to filter out stocks with
negative sentiment before recommending trades.

Usage::

    venv312/bin/python app/market/scripts/daily_sentiment_scan.py
    venv312/bin/python app/market/scripts/daily_sentiment_scan.py --limit 10  # quick test
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

from app.market.sentiment import FinbertSentimentAnalyzer
from app.market.news_fetcher import NewsFetcher

# Top 50 S&P 500 stocks by market cap (approximate, updated periodically)
# These are the most liquid, most traded stocks — sentiment matters most here
TOP_50_SP500 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "BRK.B", "LLY", "AVGO", "TSLA",
    "JPM", "V", "XOM", "UNH", "MA", "PG", "JNJ", "HD", "COST", "ABBV",
    "BAC", "MRK", "CVX", "KO", "PEP", "ORCL", "WMT", "CRM", "ADBE", "AMD",
    "NFLX", "CSCO", "TMO", "ACN", "ABT", "LIN", "DHR", "TXN", "INTC", "NEE",
    "PM", "CMG", "IBM", "QCOM", "LOW", "UPS", "SPGI", "INTU", "AMGN", "ISRG",
]

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "daily_sentiment.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_sentiment_scan")


def run_scan(limit: int = 50, headlines_per_stock: int = 10) -> dict:
    """Run the daily sentiment scan for *limit* top S&P 500 stocks.

    Parameters
    ----------
    limit : int
        Number of stocks to scan (default 50).
    headlines_per_stock : int
        Max headlines to fetch per stock (default 10).

    Returns
    -------
    dict
        Mapping ``{symbol: sentiment_summary}`` and a ``_meta`` key with
        scan metadata.
    """
    analyzer = FinbertSentimentAnalyzer()
    fetcher = NewsFetcher(min_interval=1.0)

    symbols = TOP_50_SP500[:limit]
    results: dict = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols, 1):
        logger.info("[%d/%d] Fetching headlines for %s ...", i, total, symbol)
        try:
            headlines = fetcher.fetch_headlines(symbol, limit=headlines_per_stock)

            if not headlines:
                logger.info("  No headlines found for %s, skipping", symbol)
                results[symbol] = {
                    "sentiment": "neutral",
                    "score": 0.0,
                    "headlines_analyzed": 0,
                    "breakdown": {"positive": 0, "negative": 0, "neutral": 0},
                }
                continue

            summary = analyzer.analyze_symbol(symbol, headlines=headlines)
            results[symbol] = {
                "sentiment": summary["sentiment"],
                "score": summary["score"],
                "headlines_analyzed": summary["headlines_analyzed"],
                "breakdown": summary["breakdown"],
            }
            logger.info(
                "  %s: %s (score=%.2f, n=%d)",
                symbol,
                summary["sentiment"],
                summary["score"],
                summary["headlines_analyzed"],
            )
        except Exception as exc:
            logger.error("  Error processing %s: %s", symbol, exc)
            results[symbol] = {
                "sentiment": "neutral",
                "score": 0.0,
                "headlines_analyzed": 0,
                "breakdown": {"positive": 0, "negative": 0, "neutral": 0},
                "error": str(exc),
            }

    # Add metadata
    results["_meta"] = {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "stocks_scanned": total,
        "headlines_per_stock": headlines_per_stock,
        "model": "ProsusAI/finbert",
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Daily FinBERT sentiment scan")
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Number of top S&P 500 stocks to scan (default 50)",
    )
    parser.add_argument(
        "--headlines", type=int, default=10,
        help="Max headlines to fetch per stock (default 10)",
    )
    parser.add_argument(
        "--output", type=str, default=str(OUTPUT_PATH),
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    logger.info("Starting daily sentiment scan for top %d S&P 500 stocks", args.limit)
    start = time.time()

    results = run_scan(limit=args.limit, headlines_per_stock=args.headlines)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    elapsed = time.time() - start
    logger.info("Sentiment scan complete in %.1fs. Output: %s", elapsed, output_path)

    # Print summary
    positive = sum(1 for v in results.values() if isinstance(v, dict) and v.get("sentiment") == "positive")
    negative = sum(1 for v in results.values() if isinstance(v, dict) and v.get("sentiment") == "negative")
    neutral = sum(1 for v in results.values() if isinstance(v, dict) and v.get("sentiment") == "neutral")
    logger.info("Summary: %d positive, %d negative, %d neutral", positive, negative, neutral)


if __name__ == "__main__":
    main()