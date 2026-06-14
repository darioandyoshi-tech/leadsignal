"""Nebraska Accountability and Disclosure Commission (NADC) bulk data.

URL: https://www.nebraska.gov/nadc_data/nadc_data.zip
The ZIP contains ~120 MB of pipe-delimited campaign-finance and lobbying
files.  This scraper focuses on **corporate contributors and payees** in
Omaha / Douglas / Sarpy as business-lead signals.

Signal value: organizations that donate to or are paid by Nebraska political
committees are typically established local businesses with money to spend.
"""

import csv
import io
import os
import re
import zipfile
from datetime import datetime
from typing import List, Dict

import httpx

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


ZIP_URL = "https://www.nebraska.gov/nadc_data/nadc_data.zip"
TEMP_ZIP = "/tmp/nadc_data.zip"
EXTRACT_DIR = "/tmp/nadc_data"

# Files that contain payees / contributors / corporations with city/state addresses.
TARGET_FILES = {
    "corplatefile.txt": "Corporate late filing",
    "formb1ab.txt": "Committee contributor (corporation)",
    "formb1d.txt": "Committee payee",
    "formb3.txt": "In-kind contributor",
    "formb4b3.txt": "PAC disbursement payee",
    "formb7.txt": "Contributor registration",
    "formb11.txt": "Committee recipient/expenditure",
    "forma1.txt": "Candidate committee registration",
    "commlatefile.txt": "Committee late filing",
}


def _download_zip() -> bool:
    try:
        with httpx.Client(timeout=120) as client:
            r = client.get(ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            with open(TEMP_ZIP, "wb") as f:
                f.write(r.content)
        return True
    except Exception as e:
        print(f"NADC download error: {e}")
        return False


def _extract_zip() -> None:
    with zipfile.ZipFile(TEMP_ZIP, "r") as z:
        z.extractall(EXTRACT_DIR)


def _clean_money(value: str) -> str:
    if not value:
        return ""
    v = value.strip().replace("$", "").replace(",", "")
    return v


def _is_omaha_metro(city: str, state: str, zip_code: str) -> bool:
    if state.upper() != "NE":
        return False
    metro_cities = {
        "omaha", "bellevue", "ralston", "gretna", "bennington", "valley",
        "waterloo", "boys town", "papillion", "la vista", "springfield",
        "plattsmouth", "fremont", "elkhorn",
    }
    city_clean = (city or "").lower().strip()
    if city_clean in metro_cities:
        return True
    z = (zip_code or "")[:5]
    return z in {"68102", "68104", "68105", "68106", "68107", "68108",
                 "68110", "68111", "68112", "68114", "68116", "68117",
                 "68118", "68122", "68124", "68127", "68130", "68131",
                 "68132", "68134", "68135", "68136", "68137", "68138",
                 "68142", "68144", "68152", "68154", "68164", "68178",
                 "68005", "68022", "68046", "68058", "68059", "68123",
                 "68128", "68133", "68147", "68148", "68157"}


def _find_address(row: Dict[str, str]) -> tuple:
    """Return (name, street, city, state, zip) using common column names."""
    # Name candidates
    name = (row.get("Contributor Organization Name") or
            row.get("Contributor Name") or
            row.get("Payee Name") or
            row.get("Recipient Name") or
            row.get("Corporation Name") or
            row.get("Committee Name") or
            "Unknown")
    street = (row.get("Contributor Address") or
              row.get("Payee Address") or
              row.get("Recipient Address") or
              row.get("Committee Address") or
              row.get("Agent Address") or
              "")
    city = (row.get("Contributor City") or
            row.get("Payee City") or
            row.get("Recipient City") or
            row.get("Committee City") or
            row.get("Agent City") or
            "")
    state = (row.get("Contributor State") or
             row.get("Payee State") or
             row.get("Recipient State") or
             row.get("Committee State") or
             row.get("Agent State") or
             "")
    zip_code = (row.get("Contributor Zipcode") or
                row.get("Contributor Zip") or
                row.get("Payee Zip") or
                row.get("Recipient Zip") or
                row.get("Committee Zip") or
                row.get("Agent Zip") or
                "")
    return name.strip(), street.strip(), city.strip(), state.strip(), zip_code.strip()[:10]


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except Exception:
            continue
    return None


def _process_file(path: str, label: str, limit: int) -> tuple:
    created = 0
    skipped = 0
    inspected = 0
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="|")
        for i, row in enumerate(reader):
            if i >= limit:
                break
            inspected += 1
            name, street, city, state, zip_code = _find_address(row)
            if not name or name == "Unknown":
                continue
            if not _is_omaha_metro(city, state, zip_code):
                continue
            amount = _clean_money(row.get("Amount", row.get("Cash Contribution", row.get("Expenditure Amount", ""))))
            purpose = (row.get("Purpose Of Disbursement") or
                         row.get("Expenditure Purpose") or
                         row.get("Description") or
                         "")
            date_val = (row.get("Contribution Date") or
                        row.get("Expenditure Date") or
                        row.get("Date of Disbursement") or
                        row.get("Date Received") or
                        "")
            published_at = _parse_date(date_val)

            with Session() as session:
                company = get_or_create_company(
                    session, name, city=city or "Omaha", state=state or "NE", zip_code=zip_code or None
                )
                headline = f"NADC {label}: {name[:120]}"
                if signal_exists(session, company.id, SignalType.gov_contract_award, headline):
                    skipped += 1
                    continue
                summary = f"Source: NADC {label}\nAddress: {street}, {city}, {state} {zip_code}\nAmount: ${amount if amount else 'N/A'}\nPurpose: {purpose or 'N/A'}\nDate: {published_at.date() if published_at else 'N/A'}"
                sid = insert_signal(
                    company_id=company.id,
                    signal_type=SignalType.gov_contract_award,
                    severity=1,
                    headline=headline,
                    summary=summary,
                    source_url=ZIP_URL,
                    source_api="nadc_vendors",
                    location_name=f"{city}, {state}" if city else "Omaha, NE",
                    published_at=published_at,
                    metadata={
                        "nadc_file": os.path.basename(path),
                        "nadc_label": label,
                        "address": street,
                        "city": city,
                        "state": state,
                        "zip": zip_code,
                        "amount": amount,
                        "purpose": purpose,
                    },
                    session=session,
                )
                if sid:
                    created += 1
                session.commit()
    return created, skipped, inspected


def run(limit_per_file: int = 500) -> dict:
    if not _download_zip():
        return {"source": "nadc_vendors", "signals_created": 0, "error": "download_failed"}
    _extract_zip()
    created = 0
    skipped = 0
    inspected = 0
    by_file = {}
    base_dir = os.path.join(EXTRACT_DIR, "nadc_data")
    for filename, label in TARGET_FILES.items():
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            continue
        c, s, i = _process_file(path, label, limit_per_file)
        created += c
        skipped += s
        inspected += i
        by_file[filename] = {"created": c, "skipped": s, "inspected": i}
    return {
        "source": "nadc_vendors",
        "signals_created": created,
        "signals_skipped": skipped,
        "rows_inspected": inspected,
        "by_file": by_file,
    }


if __name__ == "__main__":
    print(run())
