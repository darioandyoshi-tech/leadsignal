"""Douglas County Purchasing / Ionwave awarded-bids scraper.

Target page:
  https://douglascountypurchasing.ionwave.net/SourcingEvents.aspx?SourceType=3

SourceType values observed:
  1 = open solicitations (active bids)
  3 = awarded bids / closed events
"""

import re
import requests
from datetime import datetime, timedelta
from typing import List
from bs4 import BeautifulSoup
from decimal import Decimal, InvalidOperation

from scraper.config import DOUGLAS_BIDS_MIN_VALUE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from backend.app.models import SignalType


URL = "https://douglascountypurchasing.ionwave.net/SourcingEvents.aspx?SourceType=3"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_money(s: str) -> int:
    if not s:
        return 0
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return int(Decimal(s))
    except (InvalidOperation, ValueError):
        return 0


def _parse_date(s: str):
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _extract_rows(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr", class_=lambda c: c and ("rgRow" in c or "rgAltRow" in c)):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        title = cells[0]
        status = ""
        value = 0
        date_str = ""
        agency = "Douglas County"
        for c in cells:
            if "$" in c and value == 0:
                value = _parse_money(c)
            if any(m in c.lower() for m in ["awarded", "open", "closed", "canceled"]):
                status = c
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", c) and not date_str:
                date_str = c
        rows.append(
            {
                "title": title,
                "status": status or "awarded",
                "value": value,
                "date": _parse_date(date_str),
                "agency": agency,
                "details": " | ".join(cells),
            }
        )
    return rows


def _fetch_page(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""


def run() -> dict:
    created = 0
    skipped = 0
    inspected = 0

    html = _fetch_page(URL)
    rows = _extract_rows(html)
    cutoff = datetime.utcnow() - timedelta(days=180)

    for row in rows:
        inspected += 1
        value = row.get("value", 0)
        if value < DOUGLAS_BIDS_MIN_VALUE:
            continue
        award_date = row.get("date")
        if award_date and award_date < cutoff:
            continue

        vendor = "Douglas County / Omaha Bid Recipient"

        with Session() as session:
            company = get_or_create_company(session, vendor, city="Omaha", state="Nebraska")
            headline = f"Government bid award posted: {row['title'][:80]}"
            if signal_exists(session, company.id, SignalType.gov_contract_award, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.gov_contract_award,
                severity=2,
                headline=headline,
                summary=f"Agency: {row['agency']}\nTitle: {row['title']}\nBid Type: {row['status']}\nAward Date: {award_date.isoformat() if award_date else 'N/A'}\nNote: Award amount and vendor are not shown on the list page; detail-page automation required.",
                source_url=URL,
                source_api="douglas_bids",
                location_name="Douglas County, NE",
                published_at=award_date,
                metadata={
                    "title": row["title"],
                    "bid_type": row["status"],
                    "agency": row["agency"],
                    "award_date": award_date.isoformat() if award_date else None,
                    "detail_automation_needed": True,
                },
            )
            if sid:
                created += 1

    return {
        "source": "douglas_bids",
        "signals_created": created,
        "signals_skipped": skipped,
        "rows_inspected": inspected,
    }


if __name__ == "__main__":
    print(run())
