#!/usr/bin/env python3
"""Sync local DB with Alpaca order fills and position changes.

Run after market open to update entry prices, exit prices, realized P/L,
and order statuses based on actual Alpaca fills.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.market import AlpacaBroker
from app.models import BrokerOrder, PaperPosition, PositionStatus, OrderStatus, StockPick


async def import_unknown_alpaca_orders(broker: AlpacaBroker, db: AsyncSession):
    """Pull open and recent filled orders from Alpaca that are missing from our DB.

    This handles orders created outside LeadSignal (e.g. manual dashboard trades,
    emergency liquidation) so they still get tracked and reconciled.
    """
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, until=datetime.now(timezone.utc))
        alpaca_orders = broker.client.get_orders(req)
    except Exception:
        # Fallback: raw REST if alpaca-py API changes
        import httpx
        headers = {"APCA-API-KEY-ID": broker.api_key, "APCA-API-SECRET-KEY": broker.secret_key}
        url = "https://paper-api.alpaca.markets/v2/orders?status=all&limit=500"
        r = httpx.get(url, headers=headers, timeout=30)
        alpaca_orders = r.json() if r.status_code == 200 else []

    if not alpaca_orders:
        return 0

    # Build set of known broker_order_ids
    result = await db.execute(select(BrokerOrder.broker_order_id))
    known_ids = {row[0] for row in result.all() if row[0]}

    # Map existing positions by symbol
    result = await db.execute(select(PaperPosition).where(PaperPosition.status == PositionStatus.open))
    open_positions = result.scalars().all()
    pos_by_symbol = {p.symbol: p for p in open_positions}

    imported = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for raw in alpaca_orders:
        broker_id = str(raw.id) if not isinstance(raw, dict) else raw.get("id")
        if not broker_id or broker_id in known_ids:
            continue

        symbol = raw.symbol if not isinstance(raw, dict) else raw.get("symbol")
        side = str(raw.side).lower() if not isinstance(raw, dict) else raw.get("side", "").lower()
        status = str(raw.status) if not isinstance(raw, dict) else raw.get("status", "")
        created_at = raw.created_at if not isinstance(raw, dict) else raw.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Skip very old orders and rejected/cancelled empty orders to avoid noise
        if created_at and created_at < cutoff:
            continue
        filled_qty_val = float(getattr(raw, "filled_qty", None) or 0) if not isinstance(raw, dict) else float(raw.get("filled_qty") or 0)
        if status in ("rejected", "canceled", "cancelled") and not filled_qty_val:
            continue

        qty = (float(raw.qty) if raw.qty else None) if not isinstance(raw, dict) else (float(raw.get("qty")) if raw.get("qty") else None)
        notional = (float(raw.notional) if raw.notional else None) if not isinstance(raw, dict) else (float(raw.get("notional")) if raw.get("notional") else None)
        filled_avg = (float(raw.filled_avg_price) if raw.filled_avg_price else None) if not isinstance(raw, dict) else (float(raw.get("filled_avg_price")) if raw.get("filled_avg_price") else None)
        order_type = str(raw.order_type).lower() if not isinstance(raw, dict) else raw.get("order_type", "market").lower()

        # Find or create a position for buy orders
        position = pos_by_symbol.get(symbol)
        if position is None and side == "buy" and status not in ("rejected", "canceled", "cancelled", "expired"):
            position = PaperPosition(
                symbol=symbol,
                side="long",
                status=PositionStatus.open,
                shares=float(qty or filled_qty_val or 0),
                entry_price=filled_avg,
                entry_date=created_at or datetime.now(timezone.utc),
                notes="Imported from Alpaca (unknown origin)",
            )
            db.add(position)
            await db.flush()
            pos_by_symbol[symbol] = position

        # For sells, try to link to existing open or liquidating position
        if position is None and side == "sell":
            result = await db.execute(
                select(PaperPosition).where(
                    PaperPosition.symbol == symbol,
                    PaperPosition.status != PositionStatus.closed,
                ).order_by(PaperPosition.entry_date.desc())
            )
            position = result.scalars().first()

        order = BrokerOrder(
            position_id=position.id if position else None,
            broker="alpaca",
            side=side,
            order_type=order_type,
            symbol=symbol,
            qty=qty if qty else (filled_qty_val if filled_qty_val else None),
            notional=notional,
            broker_order_id=broker_id,
            status=OrderStatus(_normalize_order_status(status)),
            raw_response=broker._json_safe(raw.model_dump() if hasattr(raw, "model_dump") else raw),
        )
        db.add(order)
        imported += 1

    await db.commit()
    print(f"[SYNC] Imported {imported} unknown Alpaca order(s)")
    return imported


async def import_unknown_alpaca_positions(broker: AlpacaBroker, db: AsyncSession):
    """Pull open positions from Alpaca that are missing from our DB.

    This prevents the sync from closing local positions that still exist, and
    tracks positions created outside LeadSignal.
    """
    alpaca_positions = broker.get_positions()
    if not alpaca_positions or (len(alpaca_positions) == 1 and "error" in alpaca_positions[0]):
        return 0

    symbols = {p["symbol"] for p in alpaca_positions}

    result = await db.execute(
        select(PaperPosition).where(
            PaperPosition.symbol.in_(symbols),
            PaperPosition.status == PositionStatus.open,
        )
    )
    known_positions = result.scalars().all()
    known_symbols = {p.symbol for p in known_positions}

    imported = 0
    for p in alpaca_positions:
        symbol = p["symbol"]
        if symbol in known_symbols:
            continue
        if not p.get("qty"):
            continue

        position = PaperPosition(
            symbol=symbol,
            side="long",
            status=PositionStatus.open,
            shares=float(p["qty"]),
            entry_price=float(p.get("avg_entry_price", 0)) if p.get("avg_entry_price") else None,
            notional=float(p.get("market_value", 0)) if p.get("market_value") else None,
            entry_date=datetime.now(timezone.utc),
            notes="Imported from Alpaca open positions (unknown origin)",
        )
        db.add(position)
        imported += 1

    await db.commit()
    print(f"[SYNC] Imported {imported} unknown Alpaca position(s)")
    return imported


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
        await import_unknown_alpaca_positions(broker, db)
        await import_unknown_alpaca_orders(broker, db)
        # Re-fetch after imports so sync sees newly created rows
        await sync_orders(broker, db)
        await sync_positions(broker, db)

    print(f"[{datetime.now(timezone.utc)}] Sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
