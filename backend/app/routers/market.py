"""Market scan router: NASDAQ-100 daily picks and paper trading."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
    pick.exited_at = datetime.utcnow()
    pick.exit_return = exit_return
    await db.commit()
    return {"status": "exited", "pick_id": pick_id}


# ---------------------------------------------------------------------------
# Paper trading endpoints
# ---------------------------------------------------------------------------


@router.get("/account")
async def get_alpaca_account(user: Optional[User] = Depends(get_current_user_optional)):
    """Return Alpaca paper account summary."""
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured")
    broker = AlpacaBroker()
    return broker.get_account()


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
    return {"positions": positions, "count": len(positions)}


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
    return pos


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
    return {"orders": orders, "count": len(orders)}


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
    pos.exit_date = datetime.utcnow()
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
