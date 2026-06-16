"""CivicData (CKAN) historical Omaha/Douglas County permit dataset.

Live historical package:
  package: blds_permitcore_historical_aa_14757
  resource: efecb9f2-b254-4e34-90ce-4097fbe82322 (~60,859 rows, 2006-2007)

The current datastores (2016-present, 2018-current) are empty as of last check,
so this source is used for backfill and pattern training, not live signals.
"""

import io
import csv
import requests
from datetime import datetime
from typing import List

from scraper.config import (
    CIVICDATA_API_BASE,
    CIVICDATA_HISTORICAL_PACKAGE,
    CIVICDATA_HISTORICAL_RESOURCE,
)
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


def _api(action: str, **params) -> dict:
    url = f"{CIVICDATA_API_BASE}/{action}"
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def get_resource_info(resource_id: str = CIVICDATA_HISTORICAL_RESOURCE) -> dict:
    return _api("resource_show", id=resource_id)


def fetch_historical_rows(limit: int = 1000, offset: int = 0) -> List[dict]:
    """Fetch rows from the historical datastore via CKAN datastore_search API."""
    result = _api(
        "datastore_search",
        resource_id=CIVICDATA_HISTORICAL_RESOURCE,
        limit=limit,
        offset=offset,
    )
    return result.get("result", {}).get("records", [])


def fetch_csv_dump() -> List[dict]:
    """Download the full historical CSV dump if available."""
    info = get_resource_info()
    resource = info.get("result", {})
    url = resource.get("url") or resource.get("download_url")
    if not url:
        return []
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        return list(reader)
    except Exception:
        return []


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def run(limit: int = 1000) -> dict:
    """Backfill-style run: emit permit_filing signals from historical records."""
    return emit_historical_signals(limit=limit)


def emit_historical_signals(limit: int = 500) -> dict:
    """Emit permit_filing signals from historical CivicData records.

    Useful for seeding/demo; not a live feed.
    """
    rows = fetch_historical_rows(limit=limit)
    created = 0
    skipped = 0
    for row in rows:
        if row.get("PermitClass", "").upper() != "COMMERCIAL":
            continue
        cost = 0
        try:
            cost = int(float(row.get("EstProjectCost", "0") or 0))
        except Exception:
            pass
        if cost < 50000:
            continue
        contractor = row.get("ContractorCompanyName") or "Unknown Contractor"
        address = " ".join(
            p
            for p in [
                row.get("OriginalAddress1"),
                row.get("OriginalAddress2"),
                row.get("OriginalCity"),
                row.get("OriginalState"),
                row.get("OriginalZip"),
            ]
            if p
        )
        headline = f"Commercial permit (historical): {row.get('Description','Project')} in {row.get('OriginalZip','Omaha')}"
        with Session() as session:
            company = get_or_create_company(
                session, contractor, city=row.get("OriginalCity", "Omaha"), state="Nebraska"
            )
            if signal_exists(session, company.id, SignalType.permit_filing, headline):
                skipped += 1
                continue
            summary = f"Permit: {row.get('PermitNum')}\nAddress: {address}\nDescription: {row.get('Description')}\nEstimated Cost: ${cost:,.0f}\nContractor: {contractor}"
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.permit_filing,
                severity=3 if cost >= 200_000 else 2,
                headline=headline,
                summary=summary,
                source_url=row.get("Link")
                or "https://www.civicdata.com/dataset/blds_permitcore_historical_aa_14757",
                source_api="civicdata_permits_historical",
                location_name=address,
                published_at=_parse_date(row.get("IssuedDate")),
                metadata={
                    "permit_num": row.get("PermitNum"),
                    "address": address,
                    "project_cost": cost,
                    "contractor": contractor,
                    "permit_class": row.get("PermitClass"),
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()
    return {
        "source": "civicdata_permits_historical",
        "signals_created": created,
        "signals_skipped": skipped,
        "rows_fetched": len(rows),
    }


if __name__ == "__main__":
    print(run())
