"""City of Omaha building permit inspection history via CivicData.

Dataset: City of Omaha, NE-Building Permits - Inspection History since 2006
Resource ID: 2483a53a-b400-4f25-bac7-1bb7045e70b2
URL: https://www.civicdata.com/dataset/blds_inspectionhistory_v2_15761
Rows: ~883,000 inspection records.

Signal value: failed/re-inspection events indicate active construction projects
or quality issues at an address/contractor.
"""

from datetime import datetime
from typing import Dict, List

import httpx

from scraper.config import CIVICDATA_API_BASE
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


RESOURCE_ID = "2483a53a-b400-4f25-bac7-1bb7045e70b2"
DATASET_URL = f"{CIVICDATA_API_BASE}/action/datastore_search?id={RESOURCE_ID}"


def _fetch_inspections(limit: int = 500, offset: int = 0) -> List[Dict]:
    url = f"{DATASET_URL}&limit={limit}&offset={offset}"
    try:
        with httpx.Client(timeout=60) as client:
            r = client.get(
                url,
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            return r.json().get("result", {}).get("records", [])
    except Exception as e:
        print(f"CivicData inspections error: {e}")
        return []


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except Exception:
            continue
    return None


def run(limit: int = 500) -> dict:
    created = 0
    skipped = 0
    inspected = 0
    rows = _fetch_inspections(limit=limit)

    for row in rows:
        inspected += 1
        # Only capture inspections with results indicating activity or issues.
        result_code = (row.get("Result") or row.get("ResultMapped") or row.get("InspectionResult") or "").strip().upper()
        if result_code not in {"FAIL", "FAILED", "REINSPECT", "RE-INSPECT", "PARTIAL PASS", "PASS", "PASSED", "APPROVED"}:
            continue

        contractor = (row.get("ContractorCompanyName") or row.get("Contractor") or "Unknown").strip()
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
        city = (row.get("OriginalCity") or "Omaha").strip()
        state = (row.get("OriginalState") or "NE").strip()
        zip_code = str(row.get("OriginalZip") or "")[:10] or None
        inspection_date = _parse_date(row.get("InspectedDate") or row.get("ScheduledDate") or row.get("InspectionDate") or row.get("Date"))
        permit_num = row.get("PermitNum") or row.get("PermitNumber") or "N/A"

        with Session() as session:
            company = get_or_create_company(
                session, contractor, city=city, state=state, zip_code=zip_code
            )
            headline = f"Inspection {result_code.title()} for permit {permit_num} at {address[:60]}"
            if signal_exists(session, company.id, SignalType.permit_filing, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.permit_filing,
                severity=3 if result_code in {"FAIL", "FAILED", "REINSPECT", "RE-INSPECT"} else 2,
                headline=headline,
                summary=f"Permit: {permit_num}\nAddress: {address}\nInspection Type: {row.get('InspType', 'N/A')}\nInspection Result: {result_code}\nInspection Date: {inspection_date.date() if inspection_date else 'N/A'}\nInspector: {row.get('Inspector', 'N/A')}",
                source_url=row.get("Link") or DATASET_URL,
                source_api="civicdata_inspections",
                location_name=address,
                published_at=inspection_date,
                metadata={
                    "permit_num": permit_num,
                    "address": address,
                    "city": city,
                    "zip": zip_code,
                    "inspection_result": result_code,
                    "inspection_date": inspection_date.isoformat() if inspection_date else None,
                    "inspector": row.get("Inspector"),
                    "inspection_type": row.get("InspType") or row.get("InspTypeMapped"),
                    "contractor": contractor,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "civicdata_inspections",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
        "dataset_url": DATASET_URL,
    }


if __name__ == "__main__":
    print(run())
