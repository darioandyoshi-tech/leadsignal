"""Nebraska DHHS professional/occupational license search.

Public search: https://www.nebraska.gov/LISSearch/search.cgi
Bulk paid lists: https://www.nebraska.gov/hhs/lists/

The interactive search requires JavaScript; the paid bulk list portal returns
CSV/Excel downloads immediately after payment. This module is a placeholder
that documents both paths and provides a CSV ingestion helper.
"""

from datetime import datetime
from typing import List, Dict

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_URL = "https://www.nebraska.gov/LISSearch/search.cgi"
BULK_LISTS_URL = "https://www.nebraska.gov/hhs/lists/"


def run() -> dict:
    """Placeholder: HHS license search requires JavaScript / paid bulk list."""
    return {
        "source": "ne_hhs_licenses",
        "signals_created": 0,
        "status": "not_configured",
        "note": "HHS license search is JS-driven; paid bulk CSV lists available via nebraska.gov/hhs/lists/.",
        "search_url": SEARCH_URL,
        "bulk_lists_url": BULK_LISTS_URL,
        "next_step": "Purchase a bulk list for Omaha-area licenses or automate the JS search with Apify/browser automation.",
    }


def emit_from_csv(rows: List[Dict]) -> dict:
    """Emit business_license signals from a Nebraska DHHS license CSV export.

    Expected columns: License #, Prefix, First Name, Middle Name, Last Name,
    Suffix, Entity Name, License Type, Address, City, State, Zip Code, County,
    Telephone, License Status, Issue Date, Expiration Date, Email.
    """
    created = 0
    skipped = 0
    inspected = 0
    for row in rows:
        inspected += 1
        city = (row.get("City") or "Omaha").strip()
        if city.lower() != "omaha":
            continue
        entity = (row.get("Entity Name") or "").strip()
        person = f"{(row.get('First Name') or '').strip()} {(row.get('Last Name') or '').strip()}".strip()
        name = entity or person or "Unknown Licensee"
        license_num = (row.get("License #") or row.get("License#") or "").strip()
        license_type = (row.get("License Type") or "").strip()
        status = (row.get("License Status") or "").strip()
        address = " ".join(
            p for p in [row.get("Address"), row.get("Zip Code")] if p
        )
        try:
            issue_date = datetime.strptime(row["Issue Date"].strip(), "%m/%d/%Y") if row.get("Issue Date") else None
        except Exception:
            issue_date = None

        with Session() as session:
            company = get_or_create_company(
                session, name, city=city, state="Nebraska", external_ids={"hhs_license": license_num}
            )
            headline = f"DHHS license issued: {name} ({license_type})"
            if signal_exists(session, company.id, SignalType.business_license, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.business_license,
                severity=2,
                headline=headline,
                summary=f"Licensee: {name}\nLicense #: {license_num}\nType: {license_type}\nStatus: {status}\nAddress: {address}, {city}, NE",
                source_url=BULK_LISTS_URL,
                source_api="ne_hhs_licenses",
                location_name=f"{address}, {city}, NE",
                published_at=issue_date,
                metadata={
                    "license_number": license_num,
                    "license_type": license_type,
                    "license_status": status,
                    "address": address,
                    "city": city,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "ne_hhs_licenses",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
