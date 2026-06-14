
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from scraper.config import DATABASE_URL
from backend.app.models import Base, Company, Signal, SignalType

engine = create_engine(DATABASE_URL)
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
                  location_name: str = None, published_at: datetime = None, metadata: dict = None):
    with Session() as session:
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
        )
        session.add(signal)
        session.commit()
        return signal.id
