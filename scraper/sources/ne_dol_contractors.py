"""Nebraska Department of Labor contractor registration search.

Public search: https://dol.nebraska.gov/conreg/Search
The search form uses ASP.NET MVC and requires __RequestVerificationToken.
This module scrapes contractors registered in Omaha (or statewide) and emits
business_license signals.
"""

import re
from datetime import datetime
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_URL = "https://dol.nebraska.gov/conreg/Search"
SEARCH_POST_URL = "https://dol.nebraska.gov/conreg/Search/AdvancedSearch"


def _fetch_token_and_cookies() -> tuple[str, httpx.Cookies]:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        r = client.get(SEARCH_URL)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        token = token_input["value"] if token_input else ""
        return token, client.cookies


def _search_contractors(city: str = "Omaha", state: str = "NE", page: int = 1, per_page: int = 100) -> List[Dict]:
    token, cookies = _fetch_token_and_cookies()
    data = {
        "__RequestVerificationToken": token,
        "AdvancedSearch.DBAName": "",
        "AdvancedSearch.ContractorCorpName": "",
        "AdvancedSearch.City": city,
        "AdvancedSearch.State": state,
        "AdvancedSearch.ZipCode": "",
        "AdvancedSearch.PhoneNumber": "",
        "AdvancedSearch.RegistrationNumber": "",
        "Page": str(page),
        "ResultsPerPage": str(per_page),
        "TotalPages": "0",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": SEARCH_URL,
        "RequestVerificationToken": token,
    }
    with httpx.Client(timeout=30, cookies=cookies, follow_redirects=True) as client:
        r = client.post(SEARCH_POST_URL, data=data, headers=headers)
        r.raise_for_status()
    return _parse_results(r.text)


def _parse_results(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    # The result table rows contain contractor data.
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        texts = [td.get_text(strip=True) for td in tds]
        # Expected columns: Contractor, Address, Option, Expires, View Details
        if "View Details" not in " ".join(texts):
            continue
        name = texts[0] if texts else ""
        address = texts[1] if len(texts) > 1 else ""
        trade = texts[2] if len(texts) > 2 else ""
        expires = texts[3] if len(texts) > 3 else ""
        if not name:
            continue
        results.append({
            "name": name,
            "address": address,
            "trade": trade,
            "expires": expires,
        })
    return results


def _parse_expires(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except Exception:
        return None


def _extract_city_state_zip(address: str) -> tuple:
    parts = [p.strip() for p in address.split(",")]
    city = parts[-2] if len(parts) >= 2 else "Omaha"
    state_zip = parts[-1] if parts else "NE"
    state = "NE"
    zip_code = ""
    m = re.search(r"[A-Z]{2}\s*(\d{5}(-\d{4})?)", address)
    if m:
        zip_code = m.group(1)
    return city, state, zip_code


def run(city: str = "Omaha", max_pages: int = 5) -> dict:
    created = 0
    skipped = 0
    inspected = 0
    all_contractors: List[Dict] = []

    for page in range(1, max_pages + 1):
        contractors = _search_contractors(city=city, page=page, per_page=100)
        if not contractors:
            break
        all_contractors.extend(contractors)
        inspected += len(contractors)

    for contractor in all_contractors:
        name = contractor["name"]
        address = contractor["address"]
        city_name, state, zip_code = _extract_city_state_zip(address)
        trade = contractor.get("trade", "")
        expires = _parse_expires(contractor.get("expires", ""))

        with Session() as session:
            company = get_or_create_company(
                session, name, city=city_name, state=state, zip_code=zip_code or None
            )
            headline = f"Registered contractor: {name} ({trade})" if trade else f"Registered contractor: {name}"
            if signal_exists(session, company.id, SignalType.business_license, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.business_license,
                severity=2,
                headline=headline,
                summary=f"Contractor: {name}\nAddress: {address}\nTrade: {trade}\nRegistration Expires: {expires.date() if expires else 'N/A'}",
                source_url=SEARCH_URL,
                source_api="ne_dol_contractors",
                location_name=address,
                published_at=expires,
                metadata={
                    "trade": trade,
                    "address": address,
                    "city": city_name,
                    "zip": zip_code,
                    "expires": expires.isoformat() if expires else None,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "ne_dol_contractors",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }


if __name__ == "__main__":
    print(run())
