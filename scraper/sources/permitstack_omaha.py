"""PermitStack integration placeholder for live Omaha building permits.

PermitStack coverage page shows Omaha, NE with 505,643 active permits,
updated 2 days ago: https://permit-stack.com/coverage.html

This is a commercial data service. Integration steps once an API key is
available:
  1. Request API access / pricing at https://permit-stack.com
  2. Use their permits endpoint for Omaha/Douglas County.
  3. Emit permit_filing signals for commercial projects above the value threshold.

This module documents the expected schema and provides a JSON/CSV ingestion helper.
"""

from datetime import datetime
from typing import List, Dict

from scraper.config import PERMIT_MIN_PROJECT_VALUE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


COVERAGE_URL = "https://permit-stack.com/coverage.html"


def run() -> dict:
    """Placeholder: PermitStack requires a commercial API key."""
    return {
        "source": "permitstack_omaha",
        "signals_created": 0,
        "status": "not_configured",
        "note": "PermitStack has live Omaha permit data (505,643 active permits). Commercial API key required.",
        "coverage_url": COVERAGE_URL,
        "next_step": "Contact PermitStack for API key/pricing and implement their permits endpoint.",
    }


def emit_from_records(records: List[Dict]) -> dict:
    """Emit permit_filing signals from a PermitStack export.

    Expected fields: permit_number, project_type, project_value, address,
    city, state, zip, issue_date, contractor, owner, status.
    """
    created = 0
    skipped = 0
    inspected = 0
    for record in records:
        inspected += 1
        city = (record.get("city") or "Omaha").strip()
        if city.lower() != "omaha":
            continue
        value = 0
        try:
            value = int(float(str(record.get("project_value", "0")).replace("$", "").replace(",", "")))
        except Exception:
            pass
        if value < PERMIT_MIN_PROJECT_VALUE:
            continue

        contractor = (record.get("contractor") or record.get("owner") or "Unknown").strip()
        address = " ".join(
            p for p in [record.get("address"), city, record.get("state"), record.get("zip")] if p
        )
        try:
            issue_date = datetime.strptime(record["issue_date"].strip(), "%Y-%m-%d") if record.get("issue_date") else None
        except Exception:
            issue_date = None

        with Session() as session:
            company = get_or_create_company(session, contractor, city=city, state="Nebraska")
            headline = f"Permit filed: {record.get('project_type', 'Commercial project')} in {record.get('zip', 'Omaha')} valued ${value:,.0f}"
            if signal_exists(session, company.id, SignalType.permit_filing, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.permit_filing,
                severity=3 if value >= 200_000 else 2,
                headline=headline,
                summary=f"Address: {address}\nContractor/Owner: {contractor}\nValue: ${value:,.0f}\nType: {record.get('project_type', 'N/A')}\nStatus: {record.get('status', 'N/A')}",
                source_url=COVERAGE_URL,
                source_api="permitstack_omaha",
                location_name=address,
                published_at=issue_date,
                metadata={
                    "permit_number": record.get("permit_number"),
                    "project_value": value,
                    "project_type": record.get("project_type"),
                    "address": address,
                    "zip": record.get("zip"),
                    "issue_date": issue_date.isoformat() if issue_date else None,
                    "status": record.get("status"),
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
    }
