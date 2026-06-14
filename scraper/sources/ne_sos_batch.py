"""Nebraska Secretary of State new business entity filings.

The public entity search is reCAPTCHA-gated, but Nebraska SOS offers an
official paid batch search portal:
  https://www.nebraska.gov/SpecialRequestSearches/index.cgi

Cost: $15 per 1,000 records (Nebraska Revised Statutes 33-101).
This module is a stub that documents the workflow and can be enabled once a
subscriber account / API key is available.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


BATCH_URL = "https://www.nebraska.gov/SpecialRequestSearches/index.cgi"


def _search_url(from_date: str, to_date: str) -> str:
    """Build the paid batch search form URL."""
    return f"{BATCH_URL}?from={from_date}&to={to_date}"


def _format_date(d: datetime) -> str:
    return d.strftime("%m/%d/%Y")


def run(days_back: int = 7) -> dict:
    """Stub: document the paid batch search path.

    A real implementation would:
      1. Authenticate to the Nebraska SOS batch portal.
      2. POST search criteria (entity types, date range, city/county).
      3. Pay ($15/1000 records) and download CSV.
      4. Parse new Domestic/Foreign Corps, LLCs, LLPs, etc. and emit signals.
    """
    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=days_back)

    return {
        "source": "ne_sos_batch",
        "signals_created": 0,
        "status": "not_configured",
        "note": "Nebraska SOS entity search is reCAPTCHA-gated. Use the paid batch portal ($15/1000 records).",
        "batch_portal_url": BATCH_URL,
        "sample_search_url": _search_url(_format_date(from_date), _format_date(to_date)),
        "next_step": "Open a subscriber account on the batch portal and wire CSV download parsing.",
    }


def emit_from_csv(rows: List[Dict]) -> dict:
    """Emit new_business_registration signals from a Nebraska SOS CSV export.

    Expected columns include: Entity Name, Entity Type, City, State, File Date,
                            Status, Registered Agent.
    """
    created = 0
    skipped = 0
    inspected = 0
    for row in rows:
        inspected += 1
        name = (row.get("Entity Name") or row.get("Name") or "Unknown Entity").strip()
        city = (row.get("City") or "Omaha").strip()
        state = (row.get("State") or "NE").strip()
        entity_type = (row.get("Entity Type") or "Unknown").strip()
        file_date_raw = row.get("File Date") or row.get("Filing Date")
        try:
            file_date = datetime.strptime(file_date_raw.strip(), "%m/%d/%Y") if file_date_raw else None
        except Exception:
            file_date = None

        with Session() as session:
            company = get_or_create_company(
                session, name, city=city, state=state, external_ids={"ne_sos_type": entity_type}
            )
            headline = f"New {entity_type.lower()} registration: {name} ({city}, {state})"
            if signal_exists(session, company.id, SignalType.new_business_registration, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.new_business_registration,
                severity=2,
                headline=headline,
                summary=f"Entity: {name}\nType: {entity_type}\nCity: {city}, {state}\nFile Date: {file_date.date() if file_date else 'N/A'}",
                source_url=BATCH_URL,
                source_api="ne_sos_batch",
                location_name=f"{city}, {state}",
                published_at=file_date,
                metadata={
                    "entity_type": entity_type,
                    "file_date": file_date.isoformat() if file_date else None,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "ne_sos_batch",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
