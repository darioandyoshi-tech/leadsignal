"""OSHA establishment search for Omaha-area employers.

Public search: https://www.osha.gov/ords/imis/establishment.html
The search form is Oracle APEX and the results table is loaded dynamically.
A simple POST returns the same landing page, so this source needs browser
automation (Apify web-scraper or similar) to fill the form and paginate.

Search parameters:
  p_field=Estd_City
  p_filter=Omaha
  p_st=NE
  p_show=100
  p_sort=12
  p_desc=NO
  p_rownum=0
"""

import requests
from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_URL = "https://www.osha.gov/ords/imis/establishment.search"
SEARCH_FORM_URL = "https://www.osha.gov/ords/imis/establishment.html"


def _try_direct_post() -> List[Dict]:
    """Best-effort direct form POST. Usually returns no results due to JS/APEX."""
    try:
        session = requests.Session()
        session.get(SEARCH_FORM_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r = session.post(
            SEARCH_URL,
            data={
                "p_filter": "Omaha",
                "p_field": "Estd_City",
                "p_st": "NE",
                "p_show": "100",
                "p_sort": "12",
                "p_desc": "NO",
                "p_rownum": "0",
            },
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": SEARCH_FORM_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    results = []
    for link in soup.find_all("a", href=lambda x: x and "estab_detail" in x.lower()):
        results.append({
            "name": link.get_text(strip=True),
            "detail_url": "https://www.osha.gov" + link["href"] if link["href"].startswith("/") else link["href"],
        })
    return results


def run() -> dict:
    """Placeholder: OSHA search needs browser automation."""
    direct_results = _try_direct_post()
    return {
        "source": "osha_omaha",
        "signals_created": 0,
        "direct_post_establishments": len(direct_results),
        "status": "not_configured" if not direct_results else "partial",
        "note": "OSHA establishment search returns results via JS/APEX; needs Apify/browser automation.",
        "search_url": SEARCH_FORM_URL,
        "next_step": "Run apify~web-scraper with pageFunction that fills the form, clicks search, and paginates.",
    }


def emit_from_records(records: List[Dict]) -> dict:
    """Emit business_license / negative signals from OSHA inspection records.

    Expected fields: establishment_name, city, state, inspection_date,
    violation_count, detail_url.
    """
    created = 0
    skipped = 0
    inspected = 0
    for record in records:
        inspected += 1
        name = (record.get("establishment_name") or "Unknown Establishment").strip()
        city = (record.get("city") or "Omaha").strip()
        state = (record.get("state") or "NE").strip()
        violations = int(record.get("violation_count") or 0)
        if violations < 1:
            continue

        with Session() as session:
            company = get_or_create_company(session, name, city=city, state=state)
            headline = f"OSHA inspection: {name} — {violations} violations"
            if signal_exists(session, company.id, SignalType.business_license, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.business_license,
                severity=min(5, 2 + violations),
                headline=headline,
                summary=f"Establishment: {name}\nCity: {city}, {state}\nViolations: {violations}\nDetail: {record.get('detail_url', 'N/A')}",
                source_url=record.get("detail_url") or SEARCH_FORM_URL,
                source_api="osha_omaha",
                location_name=f"{city}, {state}",
                published_at=record.get("inspection_date"),
                metadata={
                    "violation_count": violations,
                    "inspection_date": str(record.get("inspection_date")) if record.get("inspection_date") else None,
                    "detail_url": record.get("detail_url"),
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "osha_omaha",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
