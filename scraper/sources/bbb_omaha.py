"""Better Business Bureau ratings and complaints for Omaha businesses.

BBB.org is aggressively anti-bot. Two viable paths:
  1. Commercial BBB API via Parse.bot / RapidAPI (paid).
  2. Apify actors such as `haketa/bbb-scraper` or `alizarin_refrigerator-owner/bbb-scraper`.

This module is a placeholder that documents the API shape and provides a
CSV/JSON ingestion helper.
"""

from datetime import datetime
from typing import List, Dict

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


BBB_SEARCH_URL = "https://www.bbb.org/us/ne/omaha"


def run() -> dict:
    """Placeholder: BBB.org requires a commercial API or Apify actor."""
    return {
        "source": "bbb_omaha",
        "signals_created": 0,
        "status": "not_configured",
        "note": "BBB.org blocks raw HTTP scraping. Use Parse.bot BBB API or an Apify BBB scraper actor.",
        "public_url": BBB_SEARCH_URL,
        "api_options": [
            "https://parse.bot/marketplace/1ef40c3e-8a31-4c6f-b71f-0b955e37035c/bbb-org-api",
            "https://apify.com/haketa/bbb-scraper",
            "https://apify.com/alizarin_refrigerator-owner/bbb-scraper",
        ],
        "next_step": "Sign up for Parse.bot or subscribe to a BBB Apify actor and provide API key/token.",
    }


def emit_from_records(records: List[Dict]) -> dict:
    """Emit negative_review_cluster signals from BBB records.

    Expected record fields: name, rating, review_count, complaint_count,
    address, city, state, zip, bbb_url.
    """
    created = 0
    skipped = 0
    inspected = 0
    for record in records:
        inspected += 1
        city = (record.get("city") or "Omaha").strip()
        if city.lower() != "omaha":
            continue
        name = (record.get("name") or "Unknown Business").strip()
        complaint_count = int(record.get("complaint_count") or 0)
        rating = record.get("rating")
        try:
            rating_float = float(rating) if rating else None
        except Exception:
            rating_float = None

        if complaint_count < 1 and (rating_float is None or rating_float >= 3.0):
            continue

        with Session() as session:
            company = get_or_create_company(
                session,
                name,
                city=city,
                state="Nebraska",
                website=record.get("bbb_url"),
            )
            headline = f"BBB alert: {name} — {complaint_count} complaints" + (f" (rating {rating_float})" if rating_float else "")
            if signal_exists(session, company.id, SignalType.negative_review_cluster, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.negative_review_cluster,
                severity=3 if complaint_count >= 3 else 2,
                headline=headline,
                summary=f"BBB Rating: {rating or 'N/A'}\nComplaints: {complaint_count}\nReview Count: {record.get('review_count', 'N/A')}\nBBB URL: {record.get('bbb_url', 'N/A')}",
                source_url=record.get("bbb_url") or BBB_SEARCH_URL,
                source_api="bbb_omaha",
                location_name=f"{record.get('address', '')}, {city}, NE",
                metadata={
                    "rating": rating_float,
                    "complaint_count": complaint_count,
                    "review_count": record.get("review_count"),
                    "bbb_url": record.get("bbb_url"),
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "bbb_omaha",
        "signals_created": created,
        "signals_skipped": skipped,
        "inspected": inspected,
    }
