"""PermitStack live Omaha building permit integration.

PermitStack API docs: https://api.permit-stack.com/docs
Coverage page: https://permit-stack.com/coverage.html

Search endpoint: GET /v1/permits/search
Key field mappings from API response:
  id, permit_number, status, category, tags, property_type,
  address_street, address_city, address_state, address_zip,
  description_raw, estimated_value, date_filed, date_issued,
  date_completed, contractor_name, jurisdiction_name, latitude, longitude.
"""

from datetime import datetime
from typing import List, Dict

import httpx

from scraper.config import (
    OMAHA,
    PERMITSTACK_API_KEY,
    PERMITSTACK_API_BASE,
    PERMITSTACK_MIN_VALUE,
)
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_URL = f"{PERMITSTACK_API_BASE}/permits/search"
COVERAGE_URL = "https://permit-stack.com/coverage.html"


def _search_permits(city: str, state: str, limit: int = 100, page: int = 1) -> List[Dict]:
    if not PERMITSTACK_API_KEY:
        return []
    params = {"city": city, "state": state, "limit": limit, "page": page}
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(
                SEARCH_URL,
                params=params,
                headers={"X-API-Key": PERMITSTACK_API_KEY, "Accept": "application/json"},
            )
            r.raise_for_status()
            return r.json().get("results", [])
    except Exception as e:
        print(f"PermitStack API error: {e}")
        return []


def _date_or_none(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _money(value) -> int:
    if value is None:
        return 0
    try:
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == ".")
        return int(float(cleaned))
    except Exception:
        return 0


def run(limit_per_page: int = 100, max_pages: int = 5) -> dict:
    if not PERMITSTACK_API_KEY:
        return {
            "source": "permitstack_omaha",
            "signals_created": 0,
            "status": "not_configured",
            "note": "PermitStack API key not configured.",
            "coverage_url": COVERAGE_URL,
        }

    created = 0
    skipped = 0
    inspected = 0
    # Use a fresh session engine per run to avoid inheriting async engine state.
    from scraper.db_client import Session as DbSession

    for page in range(1, max_pages + 1):
        results = _search_permits(OMAHA.city, OMAHA.state_code, limit=limit_per_page, page=page)
        if not results:
            break
        for record in results:
            inspected += 1
            value = _money(record.get("estimated_value"))
            category = (record.get("category") or "").upper()
            prop_type = (record.get("property_type") or "").upper()
            status = (record.get("status") or "").upper()

            # Skip cancelled and unknown-property permits with no value.
            if status == "CANCELLED":
                continue
            # Keep commercial/renovation/new construction/significant categories even if value is missing.
            valuable_category = category in {"NEW_CONSTRUCTION", "RENOVATION", "MECHANICAL", "HVAC", "FIRE_ALARM", "SIGN", "OTHER"}
            commercial = prop_type == "COMMERCIAL" or category == "OTHER"
            if value < PERMITSTACK_MIN_VALUE and not valuable_category and not commercial:
                continue

            contractor = (record.get("contractor_name") or "Unknown").strip()
            address = " ".join(
                p
                for p in [
                    record.get("address_street"),
                    record.get("address_city"),
                    record.get("address_state"),
                    record.get("address_zip"),
                ]
                if p
            )
            issued = _date_or_none(record.get("date_issued")) or _date_or_none(record.get("date_filed"))

            with DbSession() as session:
                company = get_or_create_company(
                    session, contractor, city=record.get("address_city", "Omaha"), state="Nebraska"
                )
                value_text = f" valued ${value:,.0f}" if value else ""
                headline = f"PermitStack {record.get('category', 'permit')} in {record.get('address_zip', 'Omaha')}{value_text}"
                if signal_exists(session, company.id, SignalType.permit_filing, headline):
                    skipped += 1
                    continue
                sid = insert_signal(
                    company_id=company.id,
                    signal_type=SignalType.permit_filing,
                    severity=3 if value >= 200_000 or category == "NEW_CONSTRUCTION" else 2,
                    headline=headline,
                    summary=(f"Address: {address}\nContractor: {contractor}\nValue: ${value:,.0f}" if value else f"Address: {address}\nContractor: {contractor}\nValue: not provided\nDescription: {record.get('description_raw', 'N/A')}\nStatus: {record.get('status', 'N/A')}"),
                    source_url=COVERAGE_URL,
                    source_api="permitstack_omaha",
                    location_name=address,
                    published_at=issued,
                    metadata={
                        "permit_number": record.get("permit_number"),
                        "category": record.get("category"),
                        "property_type": record.get("property_type"),
                        "address": address,
                        "zip": record.get("address_zip"),
                        "jurisdiction": record.get("jurisdiction_name"),
                        "estimated_value": value,
                        "date_filed": record.get("date_filed"),
                        "date_issued": record.get("date_issued"),
                        "date_completed": record.get("date_completed"),
                        "status": record.get("status"),
                        "description": record.get("description_raw"),
                        "permitstack_id": record.get("id"),
                    },
                    session=session,
                )
                if sid:
                    created += 1
                session.commit()

    return {
        "source": "permitstack_omaha",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
        "status": "ok" if created > 0 or inspected > 0 else "no_results",
    }


if __name__ == "__main__":
    print(run())
