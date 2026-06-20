#!/usr/bin/env python3
"""Daily HRP allocation: compute HRP weights for current open positions.

Reads open PaperPositions from the DB, computes HRP weights using recent
price history, and saves the allocation to ``app/market/data/hrp_allocation.json``.

Designed to run after market close via cron, alongside the other daily scripts.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select

from app.db import async_session_maker
from app.market.hrp_allocator import HRPAllocator
from app.models import PaperPosition, PositionStatus

logger = logging.getLogger("daily_hrp")

OUTPUT_PATH = backend_root / "app" / "market" / "data" / "hrp_allocation.json"

# HRP parameters
LOOKBACK_DAYS = 60
MAX_WEIGHT_PCT = 0.25  # concentration cap


async def get_open_position_symbols() -> list[str]:
    """Return distinct symbols from currently open paper positions."""
    async with async_session_maker() as db:
        stmt = select(PaperPosition.symbol).where(
            PaperPosition.status == PositionStatus.open
        ).distinct()
        result = await db.execute(stmt)
        symbols = [row[0] for row in result.fetchall()]
        return symbols


async def main() -> dict:
    symbols = await get_open_position_symbols()

    if not symbols:
        logger.info("No open positions — skipping HRP allocation.")
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols": [],
            "weights": {},
            "lookback_days": LOOKBACK_DAYS,
            "max_weight_pct": MAX_WEIGHT_PCT,
            "note": "No open positions",
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(output, indent=2))
        print(json.dumps(output, indent=2))
        return output

    logger.info("Computing HRP allocation for %d symbols: %s", len(symbols), symbols)

    allocator = HRPAllocator(max_weight=MAX_WEIGHT_PCT)
    weights = allocator.allocate(symbols, lookback_days=LOOKBACK_DAYS)

    if not weights:
        logger.warning("HRP returned no weights — possible data issue.")
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols": symbols,
            "weights": {},
            "lookback_days": LOOKBACK_DAYS,
            "max_weight_pct": MAX_WEIGHT_PCT,
            "note": "HRP returned empty weights (insufficient price data)",
        }
    else:
        # Verify weights sum to ~1.0
        total = sum(weights.values())
        logger.info("HRP weights for %d symbols, sum=%.6f", len(weights), total)

        # Get dollar allocation if we had a nominal $10k portfolio
        dollar_alloc = allocator.get_position_sizes(
            list(weights.keys()), total_capital=10_000.0, lookback_days=LOOKBACK_DAYS
        )

        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols": list(weights.keys()),
            "weights": weights,
            "dollar_allocation_10k": dollar_alloc,
            "lookback_days": LOOKBACK_DAYS,
            "max_weight_pct": MAX_WEIGHT_PCT,
            "weight_sum": round(total, 6),
            "excluded": [s for s in symbols if s not in weights],
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())