"""DCGIS Douglas County parcel data via ArcGIS REST.

Endpoint: https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer/0
"""

import requests
from datetime import datetime
from typing import List

from scraper.config import DCGIS_OMaha_BBOX_WGS84
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from backend.app.models import SignalType

BASE_URL = "https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer/0"
QUERY_URL = f"{BASE_URL}/query"

_LIVE_FIELDS = [
    "OBJECTID", "PIN", "OWNER_NAME", "ADDRESS1", "ADDRESS2", "OWNER_CITY",
    "OWNER_STAT", "OWNER_ZIP", "PROPERTY_A", "HOUSE", "STREET_DIR", "STREET_NAM",
    "STREET_TYP", "APARTMENT", "PROP_CITY", "PROP_ZIP", "ACRES", "SQ_FEET",
    "BLDG_SF", "BLDG_YRBLT", "BLDG_DESC", "CLASS", "TAX_DIST", "NUMBLDGS",
    "QUALITY", "CONDITION", "X_COORD", "Y_COORD",
]


def _query_parcels(
    where: str = "1=1",
    out_fields: str = "*",
    result_record_count: int = 1000,
    return_geometry: bool = False,
) -> List[dict]:
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": str(return_geometry).lower(),
        "resultRecordCount": result_record_count,
        "f": "pjson",
        "orderByFields": "OBJECTID DESC",
    }
    try:
        r = requests.get(QUERY_URL, params=params, timeout=30)
        r.raise_for_status()
    except Exception:
        return []
    data = r.json()
    return [f.get("attributes", {}) for f in data.get("features", [])]


def _format_address(parcel: dict) -> str:
    house = parcel.get("HOUSE") or ""
    dir_ = parcel.get("STREET_DIR") or ""
    name = parcel.get("STREET_NAM") or ""
    typ = parcel.get("STREET_TYP") or ""
    apt = parcel.get("APARTMENT") or ""
    street = " ".join(p for p in [house, dir_, name, typ, apt] if p).strip()
    city = parcel.get("PROP_CITY") or ""
    zip_ = parcel.get("PROP_ZIP") or ""
    parts = [street, city, zip_] if street else [parcel.get("PROPERTY_A"), city, zip_]
    return ", ".join(p for p in parts if p)


def run() -> dict:
    """Collect high-value / large commercial parcel signals."""
    created = 0
    skipped = 0
    inspected = 0

    where = "PROP_CITY = 'OMAHA' AND (ACRES >= 1.0 OR SQ_FEET >= 5000)"
    parcels = _query_parcels(
        where=where,
        out_fields=",".join(_LIVE_FIELDS),
        result_record_count=1000,
    )

    for parcel in parcels:
        inspected += 1
        owner = parcel.get("OWNER_NAME") or "Unknown Owner"
        address = _format_address(parcel)
        parcel_id = parcel.get("PIN") or str(parcel.get("OBJECTID"))
        sqft = parcel.get("SQ_FEET") or 0
        acres = parcel.get("ACRES") or 0
        bldg_yr = parcel.get("BLDG_YRBLT")

        if not address:
            continue

        with Session() as session:
            company = get_or_create_company(
                session,
                owner,
                city=parcel.get("PROP_CITY", "Omaha"),
                state="Nebraska",
                zip_code=str(parcel.get("PROP_ZIP", ""))[:10] or None,
                external_ids={"dcgis_pin": parcel_id},
            )
            headline = f"Commercial property record: {address} ({acres:.2f} ac / {sqft:,.0f} sf)"
            if signal_exists(session, company.id, SignalType.parcel_change, headline):
                skipped += 1
                continue
            summary_lines = [
                f"PIN: {parcel_id}",
                f"Address: {address}",
                f"Owner: {owner}",
                f"Acres: {acres}",
                f"Sq Ft: {sqft:,.0f}" if sqft else "",
                f"Class: {parcel.get('CLASS', 'N/A')}",
                f"Tax District: {parcel.get('TAX_DIST', 'N/A')}",
                f"Building Year Built: {int(bldg_yr) if bldg_yr else 'N/A'}",
                f"Building Description: {parcel.get('BLDG_DESC', 'N/A')}",
            ]
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.parcel_change,
                severity=3 if (acres >= 2.0 or sqft >= 15000) else 2,
                headline=headline,
                summary="\n".join(line for line in summary_lines if line),
                source_url=BASE_URL,
                source_api="dcgis_parcels",
                location_name=address,
                metadata={
                    "pin": parcel_id,
                    "acres": acres,
                    "sq_feet": sqft,
                    "class": parcel.get("CLASS"),
                    "tax_dist": parcel.get("TAX_DIST"),
                    "bldg_year_built": bldg_yr,
                    "bldg_desc": parcel.get("BLDG_DESC"),
                },
            )
            if sid:
                created += 1

    return {
        "source": "dcgis_parcels",
        "signals_created": created,
        "signals_skipped": skipped,
        "parcels_inspected": inspected,
    }


if __name__ == "__main__":
    print(run())
