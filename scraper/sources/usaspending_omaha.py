"""USASpending.gov federal awards performed in Omaha, NE.

API endpoint: https://api.usaspending.gov/api/v2/search/spending_by_award/
"""

import requests
from datetime import datetime, timedelta
from typing import List

from scraper.config import DOUGLAS_BIDS_MIN_VALUE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
HEADERS = {"Content-Type": "application/json"}


def _fetch_awards(limit: int = 100, min_amount: int = 25_000) -> List[dict]:
    payload = {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "place_of_performance_locations": [{"country": "USA", "state": "NE", "city": "Omaha"}],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Awarding Sub Agency",
            "Contract Award Type",
            "Start Date",
            "End Date",
        ],
        "sort": "Award Amount",
        "order": "desc",
        "limit": limit,
    }
    try:
        r = requests.post(URL, headers=HEADERS, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = data.get("results", [])
    return [r for r in results if (r.get("Award Amount") or 0) >= min_amount]


def _parse_award_date(s: str):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def run() -> dict:
    created = 0
    skipped = 0
    inspected = 0
    cutoff = datetime.utcnow() - timedelta(days=365)

    awards = _fetch_awards(min_amount=DOUGLAS_BIDS_MIN_VALUE)
    for award in awards:
        inspected += 1
        recipient = award.get("Recipient Name") or "Unknown Recipient"
        amount = award.get("Award Amount") or 0
        title = award.get("Award ID") or "Federal Award"
        agency = award.get("Awarding Agency") or "Federal Government"
        sub_agency = award.get("Awarding Sub Agency") or ""
        start = _parse_award_date(award.get("Start Date"))
        end = _parse_award_date(award.get("End Date"))

        if start and start < cutoff:
            continue

        with Session() as session:
            company = get_or_create_company(session, recipient, city="Omaha", state="Nebraska")
            headline = f"Federal award: {recipient} — ${amount:,.0f} ({agency})"
            if signal_exists(session, company.id, SignalType.gov_contract_award, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.gov_contract_award,
                severity=3 if amount >= 1_000_000 else 2,
                headline=headline,
                summary=f"Recipient: {recipient}\nAward ID: {title}\nAmount: ${amount:,.0f}\nAgency: {agency}\nSub Agency: {sub_agency}\nPeriod: {start.date() if start else 'N/A'} → {end.date() if end else 'N/A'}",
                source_url="https://api.usaspending.gov/",
                source_api="usaspending_omaha",
                location_name="Omaha, NE",
                published_at=start,
                metadata={
                    "award_id": title,
                    "amount": amount,
                    "agency": agency,
                    "sub_agency": sub_agency,
                    "start_date": start.isoformat() if start else None,
                    "end_date": end.isoformat() if end else None,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {"source": "usaspending_omaha", "signals_created": created, "signals_skipped": skipped, "awards_inspected": inspected}


if __name__ == "__main__":
    print(run())
