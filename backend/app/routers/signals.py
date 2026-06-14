
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import Optional
from app.db import get_db
from app.dependencies import get_current_user
from app.models import User, Signal, Company, SignalType
from app.schemas import SignalRead, SignalFilter

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/", response_model=list[SignalRead])
async def list_signals(
    signal_type: Optional[SignalType] = None,
    min_severity: int = Query(1, ge=1, le=5),
    city: Optional[str] = None,
    zip_code: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Signal).join(Company).where(Signal.severity >= min_severity)
    if signal_type:
        stmt = stmt.where(Signal.signal_type == signal_type)
    if city:
        stmt = stmt.where(Company.city.ilike(f"%{city}%"))
    if zip_code:
        stmt = stmt.where(Company.zip_code == zip_code)
    stmt = stmt.order_by(desc(Signal.detected_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stats")
async def signal_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    stmt = select(Signal.signal_type, func.count(Signal.id)).group_by(Signal.signal_type)
    result = await db.execute(stmt)
    counts = {k.value: v for k, v in result.all()}
    return {
        "hiring_spike": counts.get("hiring_spike", 0),
        "negative_review_cluster": counts.get("negative_review_cluster", 0),
        "permit_filing": counts.get("permit_filing", 0),
        "total": sum(counts.values()),
    }
