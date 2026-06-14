"""Nebraska UCC (Uniform Commercial Code) filings.

Official search portal: https://sos.nebraska.gov/business-services/uccefs-search-and-filing-center
The public web interface requires interactive login/payment for most searches,
and there is no bulk API for free public use.

Strategy:
- Use the official paid search for targeted debtor searches.
- A future integration could use a commercial UCC data provider (e.g., CSC,
  National UCC Search) or a Nebraska subscriber account.

This module is a placeholder that documents the source.
"""

from datetime import datetime

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_PORTAL = "https://sos.nebraska.gov/business-services/uccefs-search-and-filing-center"


def run() -> dict:
    """Placeholder: Nebraska UCC search is a paid interactive form."""
    return {
        "source": "ne_ucc",
        "signals_created": 0,
        "status": "not_configured",
        "note": "Nebraska UCC search requires interactive login/payment; no free bulk API found.",
        "portal_url": SEARCH_PORTAL,
        "next_step": "Set up a Nebraska UCC subscriber account or integrate a commercial UCC data provider.",
    }


def emit_from_records(records: list) -> dict:
    """Emit ucc_filing signals from a paid UCC search export.

    Expected record fields: debtor_name, secured_party, filing_number,
    filing_date, filing_type, collateral_summary, city, state.
    """
    created = 0
    skipped = 0
    inspected = 0
    for record in records:
        inspected += 1
        debtor = (record.get("debtor_name") or "Unknown Debtor").strip()
        city = (record.get("city") or "Omaha").strip()
        state = (record.get("state") or "NE").strip()
        filing_number = (record.get("filing_number") or "").strip()
        filing_date_raw = record.get("filing_date")
        try:
            filing_date = datetime.strptime(filing_date_raw.strip(), "%m/%d/%Y") if filing_date_raw else None
        except Exception:
            filing_date = None

        with Session() as session:
            company = get_or_create_company(session, debtor, city=city, state=state)
            headline = f"UCC filing: {debtor} — {record.get('filing_type', 'Filing')}"
            if signal_exists(session, company.id, SignalType.ucc_filing, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.ucc_filing,
                severity=2,
                headline=headline,
                summary=f"Debtor: {debtor}\nSecured Party: {record.get('secured_party', 'N/A')}\nFiling #: {filing_number}\nFiling Date: {filing_date.date() if filing_date else 'N/A'}\nCollateral: {record.get('collateral_summary', 'N/A')[:200]}",
                source_url=SEARCH_PORTAL,
                source_api="ne_ucc",
                location_name=f"{city}, {state}",
                published_at=filing_date,
                metadata={
                    "filing_number": filing_number,
                    "filing_type": record.get("filing_type"),
                    "secured_party": record.get("secured_party"),
                    "filing_date": filing_date.isoformat() if filing_date else None,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "ne_ucc",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
