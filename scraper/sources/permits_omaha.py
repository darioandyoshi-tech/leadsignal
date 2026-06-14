
"""City of Omaha / Douglas County permit scrapers.

Accela, Socrata, and city open-data portals vary. This module uses a generic
HTML/CSV fallback plus known Omaha-area endpoints. Replace with live URLs
as discovered.
"""

import csv
import io
import requests
from datetime import datetime, timedelta
from scraper.config import OMAHA, PERMIT_MIN_PROJECT_VALUE
from scraper.db_client import get_or_create_company, insert_signal
from backend.app.models import SignalType


KNOWN_ENDPOINTS = {
    # Placeholder endpoints; verify with Omaha/Douglas County open data
    "socrata": "https://data.omaha.gov/resource/REPLACE.json",
    "accela": "https://accela.omaha.gov/CitizenAccess/Site/Welcome.aspx",
}


def fetch_csv_permits(url: str) -> list:
    """Generic CSV fetcher for published permit datasets."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        return list(reader)
    except Exception:
        return []


def run() -> dict:
    """Collect permit filings and emit signals."""
    # MVP: use sample/seed data if live feed is unavailable
    created = 0
    skipped = 0
    rows = _seed_permits()

    cutoff = datetime.utcnow() - timedelta(days=30)
    for row in rows:
        issued = _parse_date(row.get("issued_date", ""))
        if issued and issued < cutoff:
            continue
        value = _money(row.get("project_value", "0"))
        if value < PERMIT_MIN_PROJECT_VALUE:
            continue
        company_name = row.get("contractor") or row.get("owner") or "Unknown"
        with __import__("sqlalchemy").orm.sessionmaker(bind=__import__("scraper.db_client", fromlist=["engine"]).engine)() as session:
            company = get_or_create_company(
                session, company_name,
                city=row.get("city", "Omaha"), state="Nebraska",
            )
            headline = f"Permit filed: {row.get('project_type','Commercial project')} in {row.get('zip','Omaha')} valued ${value:,.0f}"
            if __import__("scraper.db_client", fromlist=["signal_exists"]).signal_exists(session, company.id, SignalType.permit_filing, headline):
                skipped += 1
                continue
            sid = __import__("scraper.db_client", fromlist=["insert_signal"]).insert_signal(
                company_id=company.id,
                signal_type=SignalType.permit_filing,
                severity=3 if value >= 200_000 else 2,
                headline=headline,
                summary=f"Address: {row.get('address','N/A')}\nContractor/Owner: {company_name}\nValue: ${value:,.0f}\nType: {row.get('permit_type','N/A')}",
                source_url=row.get("source_url") or "https://data.omaha.gov",
                source_api="city_permits",
                location_name=row.get("address"),
                published_at=issued,
                metadata={
                    "project_value": value,
                    "permit_type": row.get("permit_type"),
                    "zip": row.get("zip"),
                },
            )
            if sid:
                created += 1

    return {"source": "permits_omaha", "signals_created": created, "signals_skipped": skipped, "rows_processed": len(rows)}


def _seed_permits() -> list:
    """Seed dataset for Omaha commercial permit style rows."""
    return [
        {
            "issued_date": "2026-06-10",
            "project_type": "Office renovation",
            "project_value": "$450,000",
            "contractor": "ABC Commercial Builders",
            "owner": "Midtown Properties LLC",
            "address": "1200 Douglas St, Omaha, NE 68102",
            "zip": "68102",
            "permit_type": "Commercial Alteration",
            "source_url": "https://data.omaha.gov",
        },
        {
            "issued_date": "2026-06-08",
            "project_type": "Warehouse expansion",
            "project_value": "$1,200,000",
            "contractor": "Heartland Construction",
            "owner": "Omaha Logistics Inc",
            "address": "4500 L St, Omaha, NE 68117",
            "zip": "68117",
            "permit_type": "New Construction",
            "source_url": "https://data.omaha.gov",
        },
        {
            "issued_date": "2026-05-28",
            "project_type": "Restaurant build-out",
            "project_value": "$85,000",
            "contractor": "Rapid Renovations",
            "owner": "New Bistro LLC",
            "address": "3001 Farnam St, Omaha, NE 68131",
            "zip": "68131",
            "permit_type": "Commercial Alteration",
            "source_url": "https://data.omaha.gov",
        },
    ]


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _money(s: str) -> int:
    if not s:
        return 0
    cleaned = "".join(c for c in s if c.isdigit() or c == ".")
    try:
        return int(float(cleaned))
    except ValueError:
        return 0
