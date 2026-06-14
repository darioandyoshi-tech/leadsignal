"""Sarpy County delinquent real property tax list.

URL: https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information
PDF link: /DocumentCenter/View/8600/2026-DELINQUENT-TAX-LIST

The PDF has no tables. It is a fixed-format list with columns:
  parcel_number | owner | address | legal_description | ... | balance
We parse the text line-by-line, identifying records by a leading parcel number
(9+ digits) and accumulating the following lines until we hit a dollar amount.
"""

import io
import re
import requests
from datetime import datetime
from typing import List

from scraper.config import DOR_DELINQ_MIN_BALANCE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


BASE_URL = "https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information"
PDF_RE = re.compile(r'href="([^"]*DocumentCenter/View/[^"]+(?:DELINQUENT|delinquent|Tax-Sale)[^"]*)"')


def _discover_pdf_url() -> str | None:
    try:
        r = requests.get(BASE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return None
    links = PDF_RE.findall(r.text)
    if not links:
        return None
    link = None
    for l in links:
        if "2026" in l and "DELINQUENT" in l.upper():
            link = l
            break
    if not link:
        link = links[0]
    if link.startswith("http"):
        return link
    return f"https://ne-sarpycounty.civicplus.com{link}"


def _download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _extract_text_lines(pdf_bytes: bytes) -> List[str]:
    try:
        import fitz
        lines = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                lines.extend(page.get_text().splitlines())
        return lines
    except Exception as e:
        print(f"Sarpy PDF text extraction error: {e}")
        return []


def _money_to_int(value: str) -> int:
    if not value:
        return 0
    try:
        s = value.replace("$", "").replace(",", "").replace(" ", "").strip()
        return int(round(float(s), 0))
    except ValueError:
        return 0


PARCEL_RE = re.compile(r"^\d{9,}")


def _parse_records(lines: List[str], min_balance: int, source_url: str) -> dict:
    created = 0
    skipped = 0
    inspected = 0

    records = []
    current = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("*Indicates Multiple Years") or "SARPY" in line or "DELINQUENT" in line or "TAX SALE" in line:
            continue
        if PARCEL_RE.match(line):
            if current:
                records.append(current)
            current = {"parcel": line.split()[0], "owner_lines": [], "address_lines": [], "balance": None, "raw": [line]}
        elif current is not None:
            current["raw"].append(line)
            # A dollar amount ending the record
            if re.match(r"^\d{1,3}(,\d{3})*\.\d{2}$", line.replace(",", "")):
                current["balance"] = _money_to_int(line)
                records.append(current)
                current = None
            else:
                # First non-empty line after parcel is usually owner; next is address.
                if not current["owner_lines"]:
                    current["owner_lines"].append(line)
                elif not current["address_lines"]:
                    current["address_lines"].append(line)
                else:
                    # Could be legal description; ignore for now.
                    pass

    if current:
        records.append(current)

    for rec in records:
        inspected += 1
        balance = rec.get("balance") or 0
        if balance < min_balance:
            continue
        owner = " ".join(rec["owner_lines"]).strip() or "Unknown Owner"
        address = " ".join(rec["address_lines"]).strip()
        parcel = rec.get("parcel", "")

        with Session() as session:
            company = get_or_create_company(
                session,
                owner,
                city="Papillion",
                state="Nebraska",
                external_ids={"sarpy_parcel": parcel} if parcel else {},
            )
            headline = f"Sarpy tax-delinquent property: {address or parcel} (${balance:,.0f})"
            if signal_exists(session, company.id, SignalType.tax_delinquency, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.tax_delinquency,
                severity=3 if balance >= 5000 else 2,
                headline=headline,
                summary=f"Owner: {owner}\nParcel/PIN: {parcel}\nAddress: {address}\nDelinquent Balance: ${balance:,.0f}",
                source_url=source_url,
                source_api="sarpy_delinquency",
                location_name=address or "Sarpy County, NE",
                metadata={
                    "parcel": parcel,
                    "address": address,
                    "delinquent_balance": balance,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {"source": "sarpy_delinquency", "signals_created": created, "signals_skipped": skipped, "inspected": inspected}


def run() -> dict:
    url = _discover_pdf_url()
    if not url:
        return {"source": "sarpy_delinquency", "signals_created": 0, "signals_skipped": 0, "inspected": 0, "error": "Could not discover PDF URL"}
    pdf_bytes = _download_pdf(url)
    if not pdf_bytes:
        return {"source": "sarpy_delinquency", "signals_created": 0, "signals_skipped": 0, "inspected": 0, "error": "Could not download PDF", "url": url}
    lines = _extract_text_lines(pdf_bytes)
    if not lines:
        return {"source": "sarpy_delinquency", "signals_created": 0, "signals_skipped": 0, "inspected": 0, "error": "PDF text extraction not available", "url": url}
    result = _parse_records(lines, DOR_DELINQ_MIN_BALANCE, url)
    result["url"] = url
    return result


if __name__ == "__main__":
    print(run())
