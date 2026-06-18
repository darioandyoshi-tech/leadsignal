"""Market scan router: NASDAQ-100 daily picks and paper trading."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.dependencies import get_current_user_optional
from app.market import AlpacaBroker, PaperPortfolioManager
from app.models import StockPick, TradeAction, User, PaperPosition, BrokerOrder, PositionStatus, OrderStatus

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/picks")
async def get_picks(
    action: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return latest NASDAQ-100 stock picks."""
    stmt = select(StockPick)
    if active_only:
        stmt = stmt.where(StockPick.is_active == True)
    if action:
        try:
            stmt = stmt.where(StockPick.action == TradeAction(action))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    stmt = stmt.order_by(StockPick.score.desc()).limit(limit)
    result = await db.execute(stmt)
    picks = result.scalars().all()
    return {"picks": picks, "count": len(picks)}


@router.get("/picks/{pick_id}")
async def get_pick(
    pick_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(StockPick).where(StockPick.id == pick_id))
    pick = result.scalar_one_or_none()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    return pick


@router.post("/picks/{pick_id}/exit")
async def exit_pick(
    pick_id: str,
    exit_return: Optional[float] = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Manually mark a pick as exited with realized return."""
    result = await db.execute(select(StockPick).where(StockPick.id == pick_id))
    pick = result.scalar_one_or_none()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    pick.is_active = False
    pick.exited_at = datetime.now(timezone.utc)
    pick.exit_return = exit_return
    await db.commit()
    return {"status": "exited", "pick_id": pick_id}


def _position_to_dict(pos: PaperPosition) -> Dict[str, Any]:
    """Serialize a PaperPosition to a JSON-safe dict."""
    return {
        "id": str(pos.id),
        "symbol": pos.symbol,
        "side": pos.side,
        "status": pos.status.value,
        "entry_price": pos.entry_price,
        "entry_date": pos.entry_date.isoformat() if pos.entry_date else None,
        "shares": pos.shares,
        "notional": pos.notional,
        "exit_price": pos.exit_price,
        "exit_date": pos.exit_date.isoformat() if pos.exit_date else None,
        "realized_pnl": pos.realized_pnl,
        "realized_return": pos.realized_return,
        "stop_loss": pos.stop_loss,
        "take_profit": pos.take_profit,
        "max_hold_days": pos.max_hold_days,
        "planned_exit_date": pos.planned_exit_date.isoformat() if pos.planned_exit_date else None,
        "stock_pick_id": str(pos.stock_pick_id) if pos.stock_pick_id else None,
        "notes": pos.notes,
        "metadata": pos.metadata_,
        "created_at": pos.created_at.isoformat() if pos.created_at else None,
        "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
    }


def _enrich_position(pos_dict: Dict[str, Any], live_prices: Dict[str, float]) -> Dict[str, Any]:
    """Add live price and unrealized P/L to a position dict."""
    current_price = live_prices.get(pos_dict["symbol"])
    entry_price = pos_dict.get("entry_price")
    shares = pos_dict.get("shares") or 0
    pos_dict["current_price"] = current_price
    if current_price and entry_price and pos_dict.get("status") == "open":
        pos_dict["unrealized_pnl"] = round((current_price - entry_price) * shares, 2)
        pos_dict["unrealized_return"] = round((current_price - entry_price) / entry_price, 4)
        pos_dict["days_held"] = (datetime.now(timezone.utc) - datetime.fromisoformat(pos_dict["entry_date"])).days if pos_dict.get("entry_date") else None
    else:
        pos_dict["unrealized_pnl"] = None
        pos_dict["unrealized_return"] = None
        pos_dict["days_held"] = None
    return pos_dict


# ---------------------------------------------------------------------------
# Paper trading endpoints
# ---------------------------------------------------------------------------


@router.get("/account")
async def get_alpaca_account(user: Optional[User] = Depends(get_current_user_optional)):
    """Return Alpaca paper account summary with total P/L."""
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")
    broker = AlpacaBroker()
    account = broker.get_account()
    if "error" in account:
        raise HTTPException(status_code=502, detail=account["error"])

    positions = broker.get_positions()
    total_market_value = sum(p.get("market_value", 0) for p in positions if "market_value" in p)
    total_unrealized_pl = sum(
        (p.get("market_value", 0) - p.get("avg_entry_price", 0) * p.get("qty", 0))
        for p in positions
        if "market_value" in p
    )

    return {
        **account,
        "open_positions_count": len(positions),
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pl, 2),
    }


@router.get("/positions")
async def get_positions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return local paper positions."""
    stmt = select(PaperPosition).order_by(PaperPosition.created_at.desc()).limit(limit)
    if status:
        try:
            stmt = stmt.where(PaperPosition.status == PositionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    result = await db.execute(stmt)
    positions = result.scalars().all()
    return {"positions": [_position_to_dict(p) for p in positions], "count": len(positions)}


@router.get("/positions/live")
async def get_positions_live(
    status: Optional[str] = Query("open"),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return paper positions merged with Alpaca live prices and unrealized P/L."""
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")

    stmt = select(PaperPosition).order_by(PaperPosition.created_at.desc())
    if status:
        try:
            stmt = stmt.where(PaperPosition.status == PositionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    positions = result.scalars().all()

    broker = AlpacaBroker()
    live_positions = broker.get_positions()
    live_prices = {p["symbol"]: p.get("current_price") for p in live_positions}

    enriched = []
    for p in positions:
        pos_dict = _position_to_dict(p)
        enriched.append(_enrich_position(pos_dict, live_prices))

    total_unrealized = sum(p.get("unrealized_pnl") or 0 for p in enriched)
    return {
        "positions": enriched,
        "count": len(enriched),
        "total_unrealized_pnl": round(total_unrealized, 2),
    }


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PaperPosition).where(PaperPosition.id == position_id))
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    return _position_to_dict(pos)


@router.get("/positions/{position_id}/live")
async def get_position_live(
    position_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return single position with live Alpaca price and unrealized P/L."""
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")

    result = await db.execute(select(PaperPosition).where(PaperPosition.id == position_id))
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    broker = AlpacaBroker()
    live_positions = broker.get_positions()
    live_prices = {p["symbol"]: p.get("current_price") for p in live_positions}
    pos_dict = _position_to_dict(pos)
    return _enrich_position(pos_dict, live_prices)


@router.get("/orders")
async def get_orders(
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return broker orders."""
    stmt = select(BrokerOrder).order_by(BrokerOrder.created_at.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(BrokerOrder.symbol == symbol)
    if status:
        try:
            stmt = stmt.where(BrokerOrder.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    result = await db.execute(stmt)
    orders = result.scalars().all()

    def order_to_dict(o: BrokerOrder) -> Dict[str, Any]:
        return {
            "id": str(o.id),
            "position_id": str(o.position_id) if o.position_id else None,
            "broker": o.broker,
            "side": o.side,
            "order_type": o.order_type,
            "symbol": o.symbol,
            "qty": o.qty,
            "notional": o.notional,
            "limit_price": o.limit_price,
            "stop_price": o.stop_price,
            "broker_order_id": o.broker_order_id,
            "status": o.status.value,
            "raw_response": o.raw_response,
            "error_message": o.error_message,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }

    return {"orders": [order_to_dict(o) for o in orders], "count": len(orders)}


@router.get("/performance")
async def get_performance(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return paper trading performance summary."""
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")

    broker = AlpacaBroker()
    account = broker.get_account()
    if "error" in account:
        raise HTTPException(status_code=502, detail=account["error"])

    # Closed positions stats
    closed_result = await db.execute(
        select(PaperPosition).where(PaperPosition.status == PositionStatus.closed)
    )
    closed = closed_result.scalars().all()

    realized_pnls = [p.realized_pnl for p in closed if p.realized_pnl is not None]
    realized_returns = [p.realized_return for p in closed if p.realized_return is not None]
    winners = [p for p in realized_pnls if p > 0]
    losers = [p for p in realized_pnls if p < 0]

    total_realized_pnl = round(sum(realized_pnls), 2) if realized_pnls else 0.0
    win_rate = round(len(winners) / len(realized_pnls), 4) if realized_pnls else 0.0
    best_trade = round(max(realized_pnls), 2) if realized_pnls else None
    worst_trade = round(min(realized_pnls), 2) if realized_pnls else None
    avg_return = round(sum(realized_returns) / len(realized_returns), 4) if realized_returns else None

    # Open positions live P/L
    open_result = await db.execute(
        select(PaperPosition).where(PaperPosition.status == PositionStatus.open)
    )
    open_positions = open_result.scalars().all()
    live_positions = broker.get_positions()
    live_prices = {p["symbol"]: p.get("current_price") for p in live_positions}

    total_unrealized_pnl = 0.0
    open_summary = []
    for p in open_positions:
        current_price = live_prices.get(p.symbol)
        unrealized = None
        unrealized_return = None
        if current_price and p.entry_price and p.shares:
            unrealized = round((current_price - p.entry_price) * p.shares, 2)
            unrealized_return = round((current_price - p.entry_price) / p.entry_price, 4)
            total_unrealized_pnl += unrealized
        days_held = (datetime.now(timezone.utc) - p.entry_date).days if p.entry_date else None
        open_summary.append({
            "symbol": p.symbol,
            "shares": p.shares,
            "entry_price": p.entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized,
            "unrealized_return": unrealized_return,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "days_held": days_held,
        })

    # Trade counts
    buy_orders_result = await db.execute(
        select(func.count(BrokerOrder.id)).where(BrokerOrder.side == "buy").where(BrokerOrder.order_type == "bracket")
    )
    total_trades = buy_orders_result.scalar() or 0

    return {
        "account": {
            "cash": account.get("cash"),
            "equity": account.get("equity"),
            "buying_power": account.get("buying_power"),
            "portfolio_value": account.get("portfolio_value"),
        },
        "open_positions": {
            "count": len(open_positions),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "positions": open_summary,
        },
        "closed_trades": {
            "count": len(closed),
            "total_realized_pnl": total_realized_pnl,
            "win_rate": win_rate,
            "winners": len(winners),
            "losers": len(losers),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "average_return": avg_return,
        },
        "combined_pnl": round(total_realized_pnl + total_unrealized_pnl, 2),
        "total_trades_submitted": total_trades,
    }


@router.post("/positions/{position_id}/liquidate")
async def liquidate_position(
    position_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Manually close a paper position via market sell."""
    result = await db.execute(select(PaperPosition).where(PaperPosition.id == position_id))
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status != PositionStatus.open:
        raise HTTPException(status_code=409, detail="Position is not open")

    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")

    broker = AlpacaBroker()
    sell = broker.submit_market_sell(pos.symbol, qty=pos.shares)
    if not sell.success:
        raise HTTPException(status_code=502, detail=sell.error or "Sell order failed")

    pos.status = PositionStatus.closed
    pos.exit_date = datetime.now(timezone.utc)
    pos.exit_price = sell.filled_avg_price
    if pos.exit_price and pos.entry_price:
        pos.realized_return = (pos.exit_price - pos.entry_price) / pos.entry_price
        pos.realized_pnl = (pos.exit_price - pos.entry_price) * pos.shares

    db.add(
        BrokerOrder(
            position_id=pos.id,
            broker="alpaca",
            side="sell",
            order_type="market",
            symbol=pos.symbol,
            qty=pos.shares,
            broker_order_id=sell.broker_order_id,
            status=OrderStatus(sell.status),
            raw_response=sell.raw,
        )
    )
    await db.commit()
    return {"status": "liquidated", "position_id": position_id, "sell_order": sell.raw}
