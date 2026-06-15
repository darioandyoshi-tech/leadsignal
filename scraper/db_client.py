"""Synchronous DB client shared by scraper modules."""

import uuid
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Make backend package importable regardless of cwd
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from scraper.config import DATABASE_URL
from app.models import Base, Company, Signal, SignalType

# SQLite: allow cross-thread usage and wait longer on write locks.
connect_args = {"check_same_thread": False, "timeout": 60} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=NullPool,
)
try:
    Base.metadata.create_all(engine)
except Exception:
    pass  # migrations / existing DB is fine

Session = sessionmaker(bind=engine)


def get_or_create_company(session, name: str, city: str = None, state: str = None, **kwargs) -> Company:
    name_clean = name.strip().lower()
    stmt = select(Company).where(Company.name.ilike(name))
    if city:
        stmt = stmt.where(Company.city.ilike(city))
    company = session.execute(stmt).scalar_one_or_none()
    if company:
        for k, v in kwargs.items():
            if v and getattr(company, k) is None:
                setattr(company, k, v)
        company.updated_at = datetime.utcnow()
        return company
    company = Company(
        id=uuid.uuid4(),
        name=name.strip(),
        city=city,
        state=state,
        **kwargs,
    )
    session.add(company)
    session.flush()
    return company


def signal_exists(session, company_id: uuid.UUID, signal_type: SignalType, headline: str, window_hours: int = 48) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    stmt = select(Signal).where(
        Signal.company_id == company_id,
        Signal.signal_type == signal_type,
        Signal.headline == headline[:512],
        Signal.detected_at >= cutoff,
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def insert_signal(company_id: uuid.UUID, signal_type: SignalType, severity: int, headline: str,
                  summary: str = None, source_url: str = None, source_api: str = None,
                  location_name: str = None, published_at: datetime = None, metadata: dict = None,
                  lat: float = None, lng: float = None, session=None):
    """Insert a signal.  If `session` is provided, the caller must commit/close it."""
    if session is None:
        with Session() as s:
            sid = insert_signal(
                company_id, signal_type, severity, headline,
                summary=summary, source_url=source_url, source_api=source_api,
                location_name=location_name, published_at=published_at,
                metadata=metadata, session=s,
            )
            if sid:
                s.commit()
            return sid
    if signal_exists(session, company_id, signal_type, headline):
        return None
    signal = Signal(
        id=uuid.uuid4(),
        company_id=company_id,
        signal_type=signal_type,
        severity=severity,
        headline=headline[:512],
        summary=summary,
        source_url=source_url,
        source_api=source_api,
        location_name=location_name,
        published_at=published_at,
        metadata=metadata or {},
        lat=lat,
        lng=lng,
    )
    session.add(signal)
    return signal.id
