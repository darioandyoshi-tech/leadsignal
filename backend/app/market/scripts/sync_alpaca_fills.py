#!/usr/bin/env python3
"""Sync local DB with Alpaca order fills and position changes.

Run after market open to update entry prices, exit prices, realized P/L,
and order statuses based on actual Alpaca fills.
"""

from __future__ import annotations

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


async def sync_orders(broker: AlpacaBroker, db: AsyncSession):
    """Update BrokerOrder rows with latest Alpaca status."""
    # Get all orders with a broker_order_id that are not already filled/rejected/cancelled
    result = await db.execute(
        select(BrokerOrder).where(
            BrokerOrder.broker_order_id.is_not(None),
            BrokerOrder.status.notin_([
                OrderStatus.filled,
                OrderStatus.rejected,
                OrderStatus.cancelled,
            ]),
        )
    )
    orders = result.scalars().all()
    print(f"[SYNC] Orders to check: {len(orders)}")

    updated = 0
    for order in orders:
        detail = broker.get_order(order.broker_order_id)
        if "error" in detail:
            print(f"[SYNC] Could not fetch order {order.broker_order_id}: {detail['error']}")
            continue

        new_status = _normalize_order_status(detail.get("status", order.status.value))
        if new_status != order.status.value:
            order.status = OrderStatus(new_status)
            updated += 1
        order.raw_response = broker._json_safe(detail)
        if order.raw_response is None:
            order.raw_response = detail

        # Fill details
        filled_qty = detail.get("filled_qty")
        filled_avg = detail.get("filled_avg_price")
        if filled_qty not in (None, "", 0, "0"):
            try:
                order.qty = float(filled_qty)
            except (TypeError, ValueError):
                pass
        if filled_avg not in (None, ""):
            try:
                if order.side == "buy":
                    order.notional = order.qty * float(filled_avg) if order.qty else order.notional
            except (TypeError, ValueError):
                pass

    await db.commit()
    print(f"[SYNC] Updated {updated} order status(es)")


def _normalize_order_status(status: str) -> str:
    s = str(status).upper().replace("ORDERSTATUS.", "")
    mapping = {
        "NEW": "pending",
        "PENDING_NEW": "pending",
        "ACCEPTED": "accepted",
        "PARTIALLY_FILLED": "partially_filled",
        "FILLED": "filled",
        "REJECTED": "rejected",
        "CANCELED": "cancelled",
        "CANCELLED": "cancelled",
        "EXPIRED": "expired",
        "DONE_FOR_DAY": "filled",
        "REPLACED": "accepted",
    }
    return mapping.get(s, s.lower())


async def sync_positions(broker: AlpacaBroker, db: AsyncSession):
    """Update PaperPosition entries based on current Alpaca positions."""
    alpaca_positions = broker.get_positions()
    alpaca_by_symbol = {p["symbol"]: p for p in alpaca_positions}

    result = await db.execute(
        select(PaperPosition).where(PaperPosition.status == PositionStatus.open)
    )
    open_positions = result.scalars().all()
    print(f"[SYNC] Local open positions: {len(open_positions)}")

    closed_count = 0
    updated_count = 0
    for pos in open_positions:
        live = alpaca_by_symbol.get(pos.symbol)
        if live is None:
            # Position no longer exists at Alpaca -> assume closed via stop/target/market sell
            exit_price = pos.exit_price or pos.take_profit or pos.stop_loss
            # Try to get realized P/L from closed orders
            orders_result = await db.execute(
                select(BrokerOrder).where(
                    BrokerOrder.position_id == pos.id,
                    BrokerOrder.side == "sell",
                    BrokerOrder.status == OrderStatus.filled,
                )
            )
            sell_orders = orders_result.scalars().all()
            if sell_orders:
                avg_exit = sum(o.qty * (o.raw_response.get("filled_avg_price") or 0) for o in sell_orders if o.qty) / sum(o.qty for o in sell_orders if o.qty)
                exit_price = avg_exit or exit_price

            pos.status = PositionStatus.closed
            pos.exit_date = datetime.now(timezone.utc)
            pos.exit_price = exit_price
            if pos.entry_price and pos.exit_price and pos.shares:
                pos.realized_return = (pos.exit_price - pos.entry_price) / pos.entry_price
                pos.realized_pnl = (pos.exit_price - pos.entry_price) * pos.shares
            closed_count += 1
            print(f"[SYNC] Closed {pos.symbol}: exit={exit_price}, pnl={pos.realized_pnl}")
        else:
            # Update entry price from actual fill if available
            if live.get("avg_entry_price") and not pos.exit_price:
                pos.entry_price = live["avg_entry_price"]
                pos.notional = round(pos.shares * pos.entry_price, 2) if pos.shares else pos.notional
                updated_count += 1

    await db.commit()
    print(f"[SYNC] Closed {closed_count} position(s), updated {updated_count} entry price(s)")


async def main():
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        print("[SYNC] Alpaca credentials not configured. Skipping.")
        return

    broker = AlpacaBroker()
    print(f"[{datetime.now(timezone.utc)}] Starting Alpaca sync...")

    async with async_session_maker() as db:
        await sync_orders(broker, db)
        await sync_positions(broker, db)

    print(f"[{datetime.now(timezone.utc)}] Sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
