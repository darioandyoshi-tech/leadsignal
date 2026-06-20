#!/usr/bin/env python3
"""Liquidate positions that have exceeded their max-hold-day limit.

Checks planned_exit_date on all open PaperPositions. If past the deadline,
submits a market sell and closes the local position record.

Run daily after market open via cron (e.g. 10:00 AM CT).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.market import AlpacaBroker
from app.models import BrokerOrder, PaperPosition, PositionStatus, OrderStatus


async def _is_market_open(broker: AlpacaBroker) -> bool:
    """Check if Alpaca paper market is currently open."""
    import httpx
    headers = {
        "APCA-API-KEY-ID": broker.api_key,
        "APCA-API-SECRET-KEY": broker.secret_key,
    }
    try:
        clock = httpx.get(
            "https://paper-api.alpaca.markets/v2/clock",
            headers=headers,
            timeout=30,
        ).json()
        return clock.get("is_open", False)
    except Exception as exc:
        print(f"[LIQUIDATE] WARN: could not check market clock: {exc}. Assuming open.")
        return True


async def main(dry_run: bool = False):
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        print("[LIQUIDATE] Alpaca credentials not configured. Skipping.")
        return

    print(f"[{datetime.now(timezone.utc)}] Starting expired position liquidation check...")
    if dry_run:
        print("[LIQUIDATE] DRY RUN - no orders will be submitted")

    broker = AlpacaBroker()

    # Guard: only liquidate during market hours (skip if market closed, unless dry_run)
    if not dry_run:
        market_open = await _is_market_open(broker)
        if not market_open:
            print("[LIQUIDATE] Market is closed. Skipping liquidation (positions will be sold at next market open).")
            return
    now = datetime.now(timezone.utc)

    async with async_session_maker() as db:
        # Find all open positions where planned_exit_date has passed
        result = await db.execute(
            select(PaperPosition).where(
                PaperPosition.status == PositionStatus.open,
                PaperPosition.planned_exit_date.is_not(None),
                PaperPosition.planned_exit_date <= now,
            )
        )
        expired = result.scalars().all()

        if not expired:
            print("[LIQUIDATE] No expired positions found.")
            return

        print(f"[LIQUIDATE] Found {len(expired)} expired position(s):")
        for pos in expired:
            print(f"  {pos.symbol} | entry={pos.entry_price} | planned_exit={pos.planned_exit_date} | age={now - pos.entry_date}")

        # Get live positions from Alpaca to confirm they still exist
        alpaca_positions = broker.get_positions()
        alpaca_by_symbol = {p["symbol"]: p for p in alpaca_positions if "symbol" in p}

        liquidated = 0
        for pos in expired:
            live = alpaca_by_symbol.get(pos.symbol)
            if not live:
                # Position already closed at Alpaca (stop/target hit) — just update local DB
                print(f"[LIQUIDATE] {pos.symbol} already closed at Alpaca. Updating local DB.")
                pos.status = PositionStatus.closed
                pos.exit_date = now
                pos.exit_price = pos.exit_price or pos.take_profit or pos.stop_loss
                if pos.entry_price and pos.exit_price and pos.shares:
                    pos.realized_return = (pos.exit_price - pos.entry_price) / pos.entry_price
                    pos.realized_pnl = (pos.exit_price - pos.entry_price) * pos.shares
                liquidated += 1
                continue

            qty = float(live["qty"])
            current_price = float(live["current_price"])

            if dry_run:
                print(f"[LIQUIDATE DRY RUN] Would sell {pos.symbol}: {qty} shares @ ~${current_price:.2f}")
                liquidated += 1
                continue

            # Cancel any existing open orders for this symbol first
            pending_sells = broker.get_pending_sell_symbols()
            if pos.symbol in pending_sells:
                print(f"[LIQUIDATE] Cancelling existing orders for {pos.symbol} before liquidation...")
                # Cancel all open orders for this symbol
                import httpx
                headers = {
                    "APCA-API-KEY-ID": broker.api_key,
                    "APCA-API-SECRET-KEY": broker.secret_key,
                }
                base = "https://paper-api.alpaca.markets"
                orders = httpx.get(f"{base}/v2/orders?status=open&limit=500", headers=headers, timeout=30).json()
                for o in orders:
                    if o.get("symbol") == pos.symbol:
                        httpx.delete(f"{base}/v2/orders/{o['id']}", headers=headers, timeout=30)
                        print(f"  Cancelled {o['id']}")

            # Submit market sell
            result = broker.submit_market_sell(symbol=pos.symbol, qty=qty)
            if not result.success:
                print(f"[LIQUIDATE] FAILED to sell {pos.symbol}: {result.error}")
                db.add(BrokerOrder(
                    position_id=pos.id,
                    broker="alpaca",
                    side="sell",
                    order_type="market",
                    symbol=pos.symbol,
                    qty=qty,
                    status=OrderStatus.rejected,
                    error_message=result.error,
                    raw_response=result.raw,
                ))
                continue

            # Update position
            exit_price = result.filled_avg_price or current_price
            pos.status = PositionStatus.closed
            pos.exit_date = now
            pos.exit_price = exit_price
            if pos.entry_price and pos.shares:
                pos.realized_return = (exit_price - pos.entry_price) / pos.entry_price
                pos.realized_pnl = (exit_price - pos.entry_price) * pos.shares

            # Record order
            broker_order_id = str(result.broker_order_id) if result.broker_order_id else None
            db.add(BrokerOrder(
                position_id=pos.id,
                broker="alpaca",
                side="sell",
                order_type="market",
                symbol=pos.symbol,
                qty=qty,
                notional=qty * exit_price,
                broker_order_id=broker_order_id,
                status=OrderStatus(result.status),
                raw_response=result.raw,
            ))

            liquidated += 1
            print(f"[LIQUIDATE] Sold {pos.symbol}: {qty} @ ~${exit_price:.2f} | P/L: ${pos.realized_pnl or 0:.2f}")

        await db.commit()
        print(f"[{datetime.now(timezone.utc)}] Done. Liquidated {liquidated} expired position(s).")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Liquidate expired paper positions past max-hold-days")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without submitting orders")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))