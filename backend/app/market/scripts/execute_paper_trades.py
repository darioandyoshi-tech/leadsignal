#!/usr/bin/env python3
"""Execute paper trades for today's top NASDAQ-100 buy picks via Alpaca.

Run after daily_market_scan.py. Only buys when forecast is positive.
Uses OCO orders to bracket exits at take-profit / stop-loss.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.market import AlpacaBroker, PaperPortfolioManager
from app.models import StockPick, TradeAction, PaperPosition, BrokerOrder, OrderStatus, PositionStatus


async def main():
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        print("[EXEC] Alpaca credentials not configured. Skipping paper trade execution.")
        return

    if not settings.alpaca_auto_trade:
        print("[EXEC] ALPACA_AUTO_TRADE=false. Skipping execution.")
        return

    print(f"[{datetime.utcnow()}] Starting paper trade execution...")

    broker = AlpacaBroker()
    account = broker.get_account()
    if "error" in account:
        print(f"[EXEC] Alpaca account error: {account['error']}")
        return
    print(f"[EXEC] Account cash: ${account['cash']:.2f} | equity: ${account['equity']:.2f}")

    open_positions = broker.get_positions()
    print(f"[EXEC] Current Alpaca open positions: {len(open_positions)}")

    async with async_session_maker() as db:
        result = await db.execute(
            select(StockPick)
            .where(StockPick.is_active == True)
            .where(StockPick.action == TradeAction.buy)
            .order_by(StockPick.score.desc())
        )
        buy_picks = result.scalars().all()
        print(f"[EXEC] Active buy picks: {len(buy_picks)}")

    # Convert ORM picks to recommendations for portfolio manager
    from app.market.recommender import StockRecommendation

    recommendations = [
        StockRecommendation(
            symbol=p.symbol,
            action=p.action.value,
            confidence=p.confidence,
            score=p.score,
            forecast_return_4d=p.forecast_return_4d,
            predicted_close_4d=p.predicted_close_4d,
            stop_loss=p.stop_loss,
            take_profit=p.take_profit,
            max_hold_days=p.max_hold_days,
            reasoning=p.reasoning or "",
            playbook=None,
        )
        for p in buy_picks
    ]
    manager = PaperPortfolioManager(broker=broker)
    plans = manager.select_picks_to_buy(recommendations, open_positions)
    print(f"[EXEC] Trade plans created: {len(plans)}")

    async with async_session_maker() as db:
        executed = 0
        for plan in plans:
            # Check if we already have a local open position for this symbol
            existing = await db.execute(
                select(PaperPosition).where(
                    PaperPosition.symbol == plan.symbol,
                    PaperPosition.status == PositionStatus.open,
                )
            )
            if existing.scalar_one_or_none():
                print(f"[EXEC] Already have open position for {plan.symbol}; skip.")
                continue

            result = manager.execute_buy(plan)
            if not result["success"]:
                print(f"[EXEC] Failed to execute {plan.symbol}: {result.get('error')}")
                # Record failed order attempt
                db.add(
                    BrokerOrder(
                        broker="alpaca",
                        side="buy",
                        order_type="bracket",
                        symbol=plan.symbol,
                        notional=plan.notional,
                        status=OrderStatus.rejected,
                        error_message=result.get("error"),
                        raw_response=result.get("order", {}),
                    )
                )
                continue

            # Find the matching StockPick record
            pick_result = await db.execute(
                select(StockPick).where(
                    StockPick.symbol == plan.symbol,
                    StockPick.is_active == True,
                )
            )
            pick = pick_result.scalar_one_or_none()

            # Record local position
            entry_price = result["order"].get("filled_avg_price") or plan.entry_price
            shares = result["order"].get("filled_qty") or plan.shares
            notional = shares * entry_price
            position = PaperPosition(
                symbol=plan.symbol,
                status=PositionStatus.open,
                entry_price=round(entry_price, 4),
                entry_date=datetime.utcnow(),
                shares=round(shares, 6),
                notional=round(notional, 2),
                stop_loss=plan.stop_loss,
                take_profit=plan.take_profit,
                max_hold_days=plan.max_hold_days,
                planned_exit_date=datetime.utcnow() + timedelta(days=plan.max_hold_days),
                stock_pick_id=pick.id if pick else None,
                notes=f"Auto-paper buy. Forecast: {pick.forecast_return_4d*100:.2f}%" if pick else "Auto-paper buy",
            )
            db.add(position)
            await db.flush()  # get position.id

            # Record bracket order
            broker_order_id = result["order"].get("broker_order_id")
            if broker_order_id is not None:
                broker_order_id = str(broker_order_id)
            db.add(
                BrokerOrder(
                    position_id=position.id,
                    broker="alpaca",
                    side="buy",
                    order_type="bracket",
                    symbol=plan.symbol,
                    qty=round(shares, 6),
                    notional=round(notional, 2),
                    broker_order_id=broker_order_id,
                    status=OrderStatus(result["order"]["status"]),
                    raw_response=result["order"]["raw"],
                )
            )

            executed += 1
            print(f"[EXEC] Bought {plan.symbol}: ${notional:.2f} @ ${entry_price:.2f}")

        await db.commit()

    print(f"[{datetime.utcnow()}] Done. Executed {executed} paper trade(s).")


if __name__ == "__main__":
    asyncio.run(main())
