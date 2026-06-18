import math
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Sequence
from collections import defaultdict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from .criteria import ScreeningCriteria, ScoringDimension
from .result import ScreeningResult
from app.models import Signal, Company


def _hours_ago(dt: datetime) -> float:
    if dt is None:
        return 9999
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def _env_criteria() -> List[ScreeningCriteria]:
    """Load custom criteria from LEADSIGNAL_SCORING_WEIGHTS env var.

    Format: dimension:weight:min_value,...  e.g.
      LEADSIGNAL_SCORING_WEIGHTS=severity:2.5:freshness:1.5:velocity:1.0
    """
    raw = os.environ.get("LEADSIGNAL_SCORING_WEIGHTS", "")
    if not raw:
        return None

    parts = raw.split(":")
    if len(parts) % 2 != 0:
        return None

    criteria: List[ScreeningCriteria] = []
    for i in range(0, len(parts), 2):
        dim_name = parts[i]
        try:
            weight = float(parts[i + 1])
        except ValueError:
            continue
        try:
            dim = ScoringDimension(dim_name)
        except ValueError:
            continue
        criteria.append(ScreeningCriteria(dim, weight=weight))

    return criteria if criteria else None


class SignalScreener:
    """Composite factor screener for LeadSignal opportunities.

    Inspired by quant factor screens, but adapted for local-market signals.
    """

    def __init__(self, criteria: Optional[List[ScreeningCriteria]] = None):
        self.criteria = criteria or _env_criteria() or self.default_criteria()

    @staticmethod
    def default_criteria() -> List[ScreeningCriteria]:
        return [
            ScreeningCriteria(ScoringDimension.SEVERITY, weight=2.0, min_value=2),
            ScreeningCriteria(ScoringDimension.FRESHNESS, weight=1.5),
            ScreeningCriteria(ScoringDimension.VELOCITY, weight=1.5),
            ScreeningCriteria(ScoringDimension.PROXIMITY, weight=1.0),
            ScreeningCriteria(ScoringDimension.DIVERSITY, weight=0.75),
            ScreeningCriteria(ScoringDimension.FORECAST, weight=1.0),
        ]

    async def screen(
        self,
        db: AsyncSession,
        days_back: int = 30,
        radius_km: float = 5.0,
        limit: int = 100,
    ) -> List[ScreeningResult]:
        since = datetime.utcnow() - timedelta(days=days_back)
        stmt = (
            select(Signal, Company)
            .join(Company)
            .where(Signal.detected_at >= since)
            .order_by(Signal.detected_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # Normalize coordinates: prefer signal lat/lng, fall back to company.
        normalized_rows = []
        for s, c in rows:
            s.lat = s.lat if s.lat is not None else c.latitude
            s.lng = s.lng if s.lng is not None else c.longitude
            normalized_rows.append((s, c))
        rows = normalized_rows

        # Precompute context
        signals = [s for s, _ in rows]
        company_signals = defaultdict(list)
        for s, c in rows:
            company_signals[s.company_id].append(s)

        # Velocity: count of same signal_type over trailing window
        velocity: Dict[str, int] = defaultdict(int)
        for s in signals:
            velocity[s.signal_type] += 1

        # Proximity: count of signals within radius
        proximity_cache: Dict[UUID, int] = {}
        for s, c in rows:
            if s.id not in proximity_cache:
                proximity_cache[s.id] = sum(
                    1
                    for other, _ in rows
                    if self._haversine(s.lat, s.lng, other.lat, other.lng) <= radius_km
                )

        results: List[ScreeningResult] = []
        for s, c in rows:
            dim_scores: Dict[str, float] = {}
            passed: List[str] = []
            failed: List[str] = []
            for crit in self.criteria:
                score = self._score_dimension(
                    crit,
                    signal=s,
                    company=c,
                    velocity=velocity,
                    proximity_count=proximity_cache.get(s.id, 0),
                    company_signal_count=len(company_signals.get(s.company_id, [])),
                )
                dim_scores[crit.dimension.value] = round(score, 4)
                if self._passes(crit, score):
                    passed.append(crit.dimension.value)
                else:
                    failed.append(crit.dimension.value)

            total_weight = sum(c.weight for c in self.criteria)
            composite = sum(dim_scores[c.dimension.value] * c.weight for c in self.criteria)
            composite = composite / total_weight if total_weight else 0

            results.append(
                ScreeningResult(
                    signal_id=s.id,
                    symbol_or_company=c.name,
                    signal_type=s.signal_type.value,
                    headline=s.headline,
                    score=round(composite, 4),
                    dimension_scores=dim_scores,
                    passed_dimensions=passed,
                    failed_dimensions=failed,
                    metadata={
                        "lat": s.lat,
                        "lng": s.lng,
                        "hours_ago": round(_hours_ago(s.detected_at), 2),
                        "velocity": velocity[s.signal_type],
                        "nearby_signals": proximity_cache.get(s.id, 0),
                        "company_signal_count": len(company_signals.get(s.company_id, [])),
                    },
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        from app.recommend import SignalPolicyEngine
        policy = SignalPolicyEngine()
        for i, r in enumerate(results, start=1):
            r.rank = i
            r.recommendation = policy.recommend(r)
        return results[:limit]

    def _score_dimension(
        self,
        criteria: ScreeningCriteria,
        signal: Signal,
        company: Company,
        velocity: Dict[str, int],
        proximity_count: int,
        company_signal_count: int,
    ) -> float:
        dim = criteria.dimension
        if dim == ScoringDimension.SEVERITY:
            return min(1.0, (signal.severity or 1) / 5.0)
        if dim == ScoringDimension.FRESHNESS:
            hours = _hours_ago(signal.detected_at)
            return max(0.0, 1.0 - (hours / 168.0))  # decay over 7 days
        if dim == ScoringDimension.VELOCITY:
            count = velocity.get(signal.signal_type, 0)
            return min(1.0, count / 10.0)
        if dim == ScoringDimension.PROXIMITY:
            return min(1.0, proximity_count / 5.0)
        if dim == ScoringDimension.DIVERSITY:
            return min(1.0, company_signal_count / 4.0)
        if dim == ScoringDimension.FORECAST:
            # Pull from signal metadata if TimesFM forecast has been attached.
            meta = signal.metadata_ or {}
            return meta.get("forecast_score", 0.5)
        if criteria.transform:
            return criteria.transform(signal)
        return 0.5

    @staticmethod
    def _passes(criteria: ScreeningCriteria, score: float) -> bool:
        if criteria.min_value is not None and score < criteria.min_value:
            return False
        if criteria.max_value is not None and score > criteria.max_value:
            return False
        return True

    @staticmethod
    def _haversine(lat1: Optional[float], lon1: Optional[float], lat2: Optional[float], lon2: Optional[float]) -> float:
        if any(v is None for v in (lat1, lon1, lat2, lon2)):
            return float("inf")
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))
