"""Sarpy County delinquent real property tax list.

URL: https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information
PDF link: /DocumentCenter/View/8600/2026-DELINQUENT-TAX-LIST
"""

import io
import re
import requests
from datetime import datetime
from typing import List

import openpyxl

from scraper.config import DOR_DELINQ_MIN_BALANCE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


BASE_URL = "https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information"
PDF_RE = re.compile(r'href="([^"]+/DocumentCenter/View/8600/[^"]+)"')


def _discover_pdf_url() -> str | None:
    try:
        r = requests.get(BASE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return None
    links = PDF_RE.findall(r.text)
    if not links:
        return None
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


def _extract_tables_from_pdf(pdf_bytes: bytes) -> List[List[str]]:
    """Best-effort PDF table extraction. Returns list of rows if tabula/pymupdf available, else empty."""
    try:
        import fitz  # pymupdf
        rows = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                tabs = page.find_tables()
                for tab in tabs.tables:
                    rows.extend(tab.extract())
        return rows
    except Exception:
        return []


def _parse_rows(rows: List[List[str]], min_balance: int, source_url: str) -> dict:
    created = 0
    skipped = 0
    inspected = 0

    headers = {}
    header_row_idx = None
    for i, row in enumerate(rows[:25]):
        vals = [str(c or "").strip() for c in row]
        lower = [v.lower() for v in vals]
        if any("owner" in v for v in lower) and any(
            "tax" in v or "amount" in v or "balance" in v or "parcel" in v for v in lower
        ):
            headers = {v.lower(): idx for idx, v in enumerate(vals) if v}
            header_row_idx = i
            break

    if not headers:
        return {"source": "sarpy_delinquency", "signals_created": 0, "signals_skipped": 0, "inspected": 0, "note": "Could not locate header row"}

    owner_idx = headers.get("owner") or next((i for i, h in headers.items() if "owner" in i), None)
    parcel_idx = headers.get("parcel") or next((i for i, h in headers.items() if "parcel" in i or "pin" in i), None)
    address_idx = headers.get("property address") or next((i for i, h in headers.items() if "address" in i or "location" in i), None)
    balance_idx = headers.get("total") or headers.get("amount") or next(
        (i for i, h in headers.items() if any(k in h for k in ["tax", "amount", "balance", "due"])), None
    )

    for row in rows[header_row_idx + 1 :]:
        inspected += 1
        owner = str(row[owner_idx] if owner_idx is not None else "").strip() or "Unknown Owner"
        parcel = str(row[parcel_idx] if parcel_idx is not None else "").strip()
        address = str(row[address_idx] if address_idx is not None else "").strip()
        balance_raw = str(row[balance_idx] if balance_idx is not None else "").strip()
        balance = 0
        try:
            balance = int(float(balance_raw.replace("$", "").replace(",", "")))
        except ValueError:
            continue

        if balance < min_balance:
            continue

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
    rows = _extract_tables_from_pdf(pdf_bytes)
    if not rows:
        return {"source": "sarpy_delinquency", "signals_created": 0, "signals_skipped": 0, "inspected": 0, "error": "PDF table extraction not available", "url": url}
    result = _parse_rows(rows, DOR_DELINQ_MIN_BALANCE, url)
    result["url"] = url
    return result


if __name__ == "__main__":
    print(run())
