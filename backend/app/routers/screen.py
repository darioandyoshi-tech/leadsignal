"""Composite scoring / factor screening router for LeadSignal."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.db import get_db
from app.dependencies import get_current_user_optional
from app.models import User
from app.scoring import SignalScreener, ScreeningResult, ScoringDimension, ScreeningCriteria, Recommendation
from app.schemas import SignalType

router = APIRouter(prefix="/screen", tags=["screen"])


class RecommendationRead(Recommendation):
    class Config:
        from_attributes = True


class ScreeningResultRead(ScreeningResult):
    """Pydantic model reusing the dataclass for response serialization."""

    recommendation: Optional[RecommendationRead] = None

    class Config:
        from_attributes = True


@router.get("/top")
async def top_opportunities(
    days_back: int = Query(30, ge=1, le=90),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    limit: int = Query(50, ge=1, le=500),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return LeadSignal opportunities ranked by composite score."""
    screener = SignalScreener()
    results = await screener.screen(db, days_back=days_back, radius_km=radius_km, limit=limit)
    return {"results": results, "count": len(results)}


@router.post("/custom")
async def custom_screen(
    criteria: List[dict],
    days_back: int = Query(30, ge=1, le=90),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    limit: int = Query(50, ge=1, le=500),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Run a custom screen by posting criteria weights/dimensions."""
    parsed = []
    for c in criteria:
        dim = ScoringDimension(c["dimension"])
        parsed.append(
            ScreeningCriteria(
                dimension=dim,
                weight=float(c.get("weight", 1.0)),
                min_value=c.get("min_value"),
                max_value=c.get("max_value"),
            )
        )
    screener = SignalScreener(parsed)
    results = await screener.screen(db, days_back=days_back, radius_km=radius_km, limit=limit)
    return {"results": results, "count": len(results)}
