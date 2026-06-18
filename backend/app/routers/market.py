"""Market scan router: NASDAQ-100 daily picks."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_optional
from app.models import StockPick, TradeAction, User

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
