"""Douglas County Register of Deeds / LandmarkWeb deed records.

Public search: https://landmarkweb.douglascounty-ne.gov/LandmarkWeb/AlphaSearchM2/AlphaSearchIndexM2
The site loads a JavaScript disclaimer that must be accepted before searching.
Most documents require subscription/payment. Free index search only confirms
recording date, document type, and grantor/grantee names.

This module is a placeholder for browser-automation access; for bulk deeds,
use ODR deed RSS feed or DCGIS parcel ownership changes.
"""

from datetime import datetime
from typing import List, Dict

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


SEARCH_URL = "https://landmarkweb.douglascounty-ne.gov/LandmarkWeb/AlphaSearchM2/AlphaSearchIndexM2"


def run() -> dict:
    """Placeholder: LandmarkWeb requires disclaimer acceptance + subscription."""
    return {
        "source": "landmarkweb_deeds",
        "signals_created": 0,
        "status": "not_configured",
        "note": "LandmarkWeb requires JS disclaimer acceptance and paid document access; not currently automatable without browser automation + subscription.",
        "search_url": SEARCH_URL,
        "alternative_sources": [
            "odr_feeds (deeds RSS)",
            "dcgis_parcels (parcel ownership changes)",
        ],
        "next_step": "If deed alerts are required, subscribe to LandmarkWeb or use a title-data provider; otherwise rely on ODR/DGIS signals.",
    }


def emit_from_records(records: List[Dict]) -> dict:
    """Emit parcel_change signals from LandmarkWeb index records.

    Expected fields: grantor, grantee, document_type, recording_date,
    book/page, instrument_number, legal_description.
    """
    created = 0
    skipped = 0
    inspected = 0
    for record in records:
        inspected += 1
        grantee = (record.get("grantee") or "Unknown Grantee").strip()
        city = (record.get("city") or "Omaha").strip()
        document_type = (record.get("document_type") or "").strip()
        try:
            recording_date = datetime.strptime(record["recording_date"].strip(), "%m/%d/%Y") if record.get("recording_date") else None
        except Exception:
            recording_date = None

        with Session() as session:
            company = get_or_create_company(session, grantee, city=city, state="Nebraska")
            headline = f"Deed recorded: {grantee} — {document_type}"
            if signal_exists(session, company.id, SignalType.parcel_change, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.parcel_change,
                severity=2,
                headline=headline,
                summary=f"Grantor: {record.get('grantor', 'N/A')}\nGrantee: {grantee}\nDocument: {document_type}\nRecording Date: {recording_date.date() if recording_date else 'N/A'}\nInstrument #: {record.get('instrument_number', 'N/A')}",
                source_url=SEARCH_URL,
                source_api="landmarkweb_deeds",
                location_name=f"{city}, NE",
                published_at=recording_date,
                metadata={
                    "document_type": document_type,
                    "grantor": record.get("grantor"),
                    "grantee": grantee,
                    "recording_date": recording_date.isoformat() if recording_date else None,
                    "instrument_number": record.get("instrument_number"),
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "landmarkweb_deeds",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
