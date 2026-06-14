
"""Omaha Accela Citizen Access permit scraper.

Accela portals are JavaScript-heavy and require session management. This module
provides a best-effort scraper that falls back to seed data when the portal
cannot be reached or parsed reliably.

To make this robust, you typically need:
- Selenium/Playwright for the search form
- Session cookies after landing on CapHome.aspx
- Parsing of the search results grid

For MVP, we attempt a lightweight request and fall back to seed permits.
"""

import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from scraper.config import OMAHA, PERMIT_MIN_PROJECT_VALUE
from scraper.db_client import get_or_create_company, insert_signal
from scraper.sources.permits_omaha import _seed_permits
from backend.app.models import SignalType

BASE_URL = "https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx"
SEARCH_URL = "https://aca-prod.accela.com/OMAHA/Cap/CapSearch.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_permits() -> list:
    """Attempt to fetch recent permits from Accela. Returns empty list on failure."""
    try:
        session = requests.Session()
        # Get initial session/cookies
        r = session.get(BASE_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()

        # Accela search forms have complex ASP.NET viewstate; this is a placeholder
        # for a real implementation using Selenium/Playwright.
        # For now, return empty so we don't emit garbage signals.
        return []
    except Exception:
        return []


def run() -> dict:
    """Collect permit filings and emit signals."""
    rows = fetch_permits()
    if not rows:
        # Fallback to seed data for MVP demo
        rows = _seed_permits()

    cutoff = datetime.utcnow() - timedelta(days=30)
    created = 0
    skipped = 0

    for row in rows:
        issued = None
        if row.get("issued_date"):
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    issued = datetime.strptime(row["issued_date"], fmt)
                    break
                except ValueError:
                    continue
        if issued and issued < cutoff:
            continue

        value = 0
        if row.get("project_value"):
            cleaned = "".join(c for c in row["project_value"] if c.isdigit() or c == ".")
            try:
                value = int(float(cleaned))
            except ValueError:
                pass
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
                source_url=row.get("source_url") or "https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx",
                source_api="accela_omaha",
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

    return {"source": "accela_omaha", "signals_created": created, "signals_skipped": skipped, "rows_processed": len(rows), "live_fetch": len(rows) != len(_seed_permits())}
