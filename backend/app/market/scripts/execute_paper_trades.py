#!/usr/bin/env python3
"""Execute paper trades for today's top NASDAQ-100 buy picks via Alpaca.

Run after daily_market_scan.py. Only buys when forecast is positive.
Uses OCO orders to bracket exits at take-profit / stop-loss.
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
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


async def main(dry_run: bool = False):
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        print("[EXEC] Alpaca credentials not configured. Skipping paper trade execution.")
        return

    if not settings.alpaca_auto_trade:
        print("[EXEC] ALPACA_AUTO_TRADE=false. Skipping execution.")
        return

    print(f"[{datetime.now(timezone.utc)}] Starting paper trade execution...")
    if dry_run:
        print("[EXEC] DRY RUN - no orders will be submitted")

    broker = AlpacaBroker()
    account = broker.get_account()
    if "error" in account:
        print(f"[EXEC] Alpaca account error: {account['error']}")
        return
    print(f"[EXEC] Account cash: ${account['cash']:.2f} | equity: ${account['equity']:.2f}")

    # Circuit breaker: daily max loss
    async with async_session_maker() as db:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        from sqlalchemy import func
        daily_pnl_result = await db.execute(
            select(func.coalesce(func.sum(PaperPosition.realized_pnl), 0.0)).where(
                PaperPosition.status == PositionStatus.closed,
                PaperPosition.exit_date >= today_start,
            )
        )
        daily_realized_pnl = float(daily_pnl_result.scalar() or 0.0)
        print(f"[EXEC] Today's realized P/L: ${daily_realized_pnl:.2f}")
        if daily_realized_pnl <= -settings.alpaca_daily_max_loss:
            print(f"[EXEC] CIRCUIT BREAKER: daily max loss ${settings.alpaca_daily_max_loss:.2f} hit. No new trades.")
            return

        # Circuit breaker: portfolio heat (cash deployed vs equity)
        open_positions_result = await db.execute(
            select(PaperPosition).where(PaperPosition.status == PositionStatus.open)
        )
        open_positions = open_positions_result.scalars().all()
        # Use current Alpaca positions for accurate market value, fall back to notional
        alpaca_positions = broker.get_positions()
        alpaca_mv = {p["symbol"]: float(p.get("market_value", 0)) for p in alpaca_positions if "symbol" in p}
        open_positions_value = sum(
            alpaca_mv.get(p.symbol, p.notional or 0) for p in open_positions
        )
        equity = float(account.get("equity", account.get("portfolio_value", 0)))
        heat = open_positions_value / equity if equity > 0 else 0
        print(f"[EXEC] Portfolio heat: {heat:.2%} (${open_positions_value:.2f} deployed / ${equity:.2f} equity)")
        if heat >= settings.alpaca_max_portfolio_heat:
            print(f"[EXEC] CIRCUIT BREAKER: max portfolio heat {settings.alpaca_max_portfolio_heat:.2%} hit. No new trades.")
            return

    open_positions = broker.get_positions()
    print(f"[EXEC] Current Alpaca open positions: {len(open_positions)}")
    open_symbols = {p["symbol"] for p in open_positions}

    # Also skip symbols with pending sell orders (liquidation in progress)
    pending_sell_symbols = broker.get_pending_sell_symbols()
    print(f"[EXEC] Symbols with pending sells: {len(pending_sell_symbols)}")
    skip_symbols = open_symbols | pending_sell_symbols
    print(f"[EXEC] Skipping {len(skip_symbols)} symbols: {sorted(skip_symbols)}")

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
    import yfinance as yf

    # Fetch current prices for all buy picks so position sizing uses real entry price
    pick_symbols = [p.symbol for p in buy_picks]
    current_prices = {}
    if pick_symbols:
        try:
            tickers = yf.Tickers(" ".join(pick_symbols))
            for sym in pick_symbols:
                try:
                    hist = tickers.tickers[sym].history(period="1d", interval="1m")
                    if not hist.empty:
                        current_prices[sym] = float(hist["Close"].iloc[-1])
                except Exception:
                    pass
        except Exception as exc:
            print(f"[EXEC] WARN fetching current prices: {exc}")
    print(f"[EXEC] Fetched current prices for {len(current_prices)}/{len(pick_symbols)} symbols")

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
    plans = manager.select_picks_to_buy(recommendations, skip_symbols, current_prices=current_prices)
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

            if dry_run:
                print(f"[EXEC DRY RUN] Would buy {plan.symbol}: ${plan.notional:.2f} @ ${plan.entry_price:.2f}")
                executed += 1
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
                entry_date=datetime.now(timezone.utc),
                shares=round(shares, 6),
                notional=round(notional, 2),
                stop_loss=plan.stop_loss,
                take_profit=plan.take_profit,
                max_hold_days=plan.max_hold_days,
                planned_exit_date=datetime.now(timezone.utc) + timedelta(days=plan.max_hold_days),
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

    print(f"[{datetime.now(timezone.utc)}] Done. Executed {executed} paper trade(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute paper trades for daily NASDAQ-100 picks")
    parser.add_argument("--dry-run", action="store_true", help="Print trades without submitting orders")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
