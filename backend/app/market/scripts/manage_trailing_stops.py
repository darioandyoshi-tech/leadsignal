#!/usr/bin/env python3
"""Trailing stop and breakeven activation manager for open paper positions.

For each open position:
1. Fetch current price from Alpaca
2. If price has moved 50% toward take_profit → move stop to entry (breakeven)
3. If price has moved 75% toward take_profit → trail stop to lock in 50% of gains
4. If trailing stop is hit → submit market sell

Run every 30 minutes during market hours via cron.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from app.config import get_settings
from app.db import async_session_maker
from app.market import AlpacaBroker
from app.models import BrokerOrder, PaperPosition, PositionStatus, OrderStatus


async def manage_trailing_stops(broker: AlpacaBroker, dry_run: bool = False):
    """Adjust stops on open positions based on current price movement."""
    # Get live positions with current prices
    alpaca_positions = broker.get_positions()
    if not alpaca_positions or (len(alpaca_positions) == 1 and "error" in alpaca_positions[0]):
        print("[TRAIL] No live positions at Alpaca.")
        return 0

    live_by_symbol = {p["symbol"]: p for p in alpaca_positions if "symbol" in p}

    async with async_session_maker() as db:
        result = await db.execute(
            select(PaperPosition).where(PaperPosition.status == PositionStatus.open)
        )
        open_positions = result.scalars().all()

        adjustments = 0
        for pos in open_positions:
            live = live_by_symbol.get(pos.symbol)
            if not live:
                continue

            current_price = float(live["current_price"])
            entry = pos.entry_price
            stop = pos.stop_loss
            target = pos.take_profit

            if not entry or not stop or not target:
                continue

            # Calculate progress toward take profit
            tp_distance = target - entry
            if tp_distance <= 0:
                continue

            progress = (current_price - entry) / tp_distance

            # Phase 1: Breakeven activation (50% progress)
            if progress >= 0.50 and stop < entry:
                new_stop = entry  # Move stop to breakeven
                print(f"[TRAIL] {pos.symbol}: Breakeven activation. price={current_price:.2f} progress={progress:.0%} stop {stop:.2f} → {new_stop:.2f}")
                if not dry_run:
                    pos.stop_loss = new_stop
                    adjustments += 1

            # Phase 2: Trailing stop (75% progress → lock in 50% of gains)
            if progress >= 0.75:
                locked_gain = entry + (tp_distance * 0.50)
                if stop < locked_gain:
                    new_stop = round(locked_gain, 2)
                    print(f"[TRAIL] {pos.symbol}: Trailing stop. price={current_price:.2f} progress={progress:.0%} stop {stop:.2f} → {new_stop:.2f}")
                    if not dry_run:
                        pos.stop_loss = new_stop
                        adjustments += 1

            # Phase 3: If current price has hit the stop, liquidate
            if current_price <= stop:
                qty = float(live["qty"])
                print(f"[TRAIL] {pos.symbol}: STOP HIT at {current_price:.2f} (stop={stop:.2f}). Liquidating {qty} shares.")
                if not dry_run:
                    result = broker.submit_market_sell(symbol=pos.symbol, qty=qty)
                    if result.success:
                        pos.status = PositionStatus.closed
                        pos.exit_date = datetime.now(timezone.utc)
                        pos.exit_price = result.filled_avg_price or current_price
                        if pos.entry_price and pos.shares:
                            pos.realized_return = (pos.exit_price - pos.entry_price) / pos.entry_price
                            pos.realized_pnl = (pos.exit_price - pos.entry_price) * pos.shares
                        broker_order_id = str(result.broker_order_id) if result.broker_order_id else None
                        db.add(BrokerOrder(
                            position_id=pos.id,
                            broker="alpaca",
                            side="sell",
                            order_type="market",
                            symbol=pos.symbol,
                            qty=qty,
                            broker_order_id=broker_order_id,
                            status=OrderStatus(result.status),
                            raw_response=result.raw,
                        ))
                        adjustments += 1
                    else:
                        print(f"[TRAIL] FAILED to liquidate {pos.symbol}: {result.error}")

        await db.commit()
        print(f"[TRAIL] Adjusted {adjustments} position(s).")
        return adjustments


async def main(dry_run: bool = False):
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        print("[TRAIL] Alpaca credentials not configured. Skipping.")
        return

    print(f"[{datetime.now(timezone.utc)}] Starting trailing stop management...")
    if dry_run:
        print("[TRAIL] DRY RUN - no orders will be submitted")

    broker = AlpacaBroker()

    # Check if market is open
    import httpx
    headers = {
        "APCA-API-KEY-ID": broker.api_key,
        "APCA-API-SECRET-KEY": broker.secret_key,
    }
    clock = httpx.get("https://paper-api.alpaca.markets/v2/clock", headers=headers, timeout=30).json()
    if not clock.get("is_open", False):
        print("[TRAIL] Market is closed. Skipping trailing stop management.")
        return

    await manage_trailing_stops(broker, dry_run=dry_run)
    print(f"[{datetime.now(timezone.utc)}] Done.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage trailing stops on open paper positions")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without submitting orders")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))