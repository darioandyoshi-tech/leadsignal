
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from typing import Optional
from app.db import get_db
from app.dependencies import get_current_user_optional
from app.models import User, Signal, Company, SignalType
from app.schemas import SignalRead, SignalFilter

router = APIRouter(prefix="/signals", tags=["signals"])


PERMIT_SUBTYPE_KEYWORDS = [
    ("electrical", "electrical"),
    ("mechanical", "mechanical"),
    ("plumbing", "plumbing"),
    ("wrecking_demolition", "wreck"),
    ("wrecking_demolition", "demolition"),
    ("building", "building"),
    ("building", "construction"),
    ("building", "remodel"),
    ("building", "addition"),
    ("building", "tenant improvement"),
    ("inspection", "inspection"),
]


def _classify_permit_subtype(signal) -> str:
    text = f"{signal.headline or ''} {signal.summary or ''} {signal.source_api or ''}".lower()
    for subtype, keyword in PERMIT_SUBTYPE_KEYWORDS:
        if keyword in text:
            return subtype
    return "other"


@router.get("/", response_model=list[SignalRead])
async def list_signals(
    signal_type: Optional[SignalType] = None,
    min_severity: int = Query(1, ge=1, le=5),
    city: Optional[str] = None,
    zip_code: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    # Public read access for MVP demo; paid tiers can gate later.
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
async def signal_stats(user: Optional[User] = Depends(get_current_user_optional), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    stmt = select(Signal.signal_type, func.count(Signal.id)).group_by(Signal.signal_type)
    result = await db.execute(stmt)
    counts = {k.value: v for k, v in result.all()}

    # Break permit_filing into subtypes by scanning headline/summary/source_api.
    permit_subtypes = {
        "building": 0,
        "electrical": 0,
        "mechanical": 0,
        "plumbing": 0,
        "wrecking_demolition": 0,
        "inspection": 0,
        "other": 0,
    }
    permit_stmt = select(Signal).where(Signal.signal_type == SignalType.permit_filing)
    permit_result = await db.execute(permit_stmt)
    for signal in permit_result.scalars().all():
        subtype = _classify_permit_subtype(signal)
        permit_subtypes[subtype] = permit_subtypes.get(subtype, 0) + 1

    return {
        "hiring_spike": counts.get("hiring_spike", 0),
        "negative_review_cluster": counts.get("negative_review_cluster", 0),
        "permit_filing": counts.get("permit_filing", 0),
        "permit_subtypes": permit_subtypes,
        "parcel_change": counts.get("parcel_change", 0),
        "tax_delinquency": counts.get("tax_delinquency", 0),
        "gov_contract_award": counts.get("gov_contract_award", 0),
        "business_license": counts.get("business_license", 0),
        "ucc_filing": counts.get("ucc_filing", 0),
        "new_business_registration": counts.get("new_business_registration", 0),
        "total": sum(counts.values()),
    }
