
"""Google Places API review monitoring for Omaha businesses."""

import os
import requests
from datetime import datetime, timedelta
from scraper.config import OMAHA, TARGET_INDUSTRIES, REVIEW_CLUSTER_MIN_REVIEWS, REVIEW_CLUSTER_MAX_STARS
from scraper.db_client import get_or_create_company, insert_signal
from backend.app.models import SignalType

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
PLACES_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def search_places(query: str, location: str = "Omaha, NE", radius: int = 25000, max_pages: int = 3) -> list:
    if not API_KEY:
        return []
    places = []
    params = {
        "query": query,
        "location": "41.2565,-95.9345",
        "radius": radius,
        "key": API_KEY,
    }
    next_token = True
    page = 0
    while next_token and page < max_pages:
        try:
            r = requests.get(PLACES_TEXTSEARCH_URL, params=params, timeout=20)
            r.raise_for_status()
        except Exception:
            break
        data = r.json()
        places.extend(data.get("results", []))
        next_token = data.get("next_page_token")
        if next_token:
            params = {"pagetoken": next_token, "key": API_KEY}
            __import__("time").sleep(2)
        else:
            next_token = False
        page += 1
    return places


def get_place_details(place_id: str) -> dict:
    if not API_KEY:
        return {}
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,website,url,reviews,types",
        "key": API_KEY,
    }
    try:
        r = requests.get(PLACE_DETAILS_URL, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("result", {})
    except Exception:
        return {}


def run() -> dict:
    if not API_KEY:
        return {"source": "google_reviews", "signals_created": 0, "skipped": 0, "error": "No GOOGLE_PLACES_API_KEY"}

    cutoff = datetime.utcnow() - timedelta(days=14)
    created = 0
    skipped = 0
    inspected = 0

    for industry in TARGET_INDUSTRIES[:10]:  # limit API spend during MVP
        query = f"{industry} in Omaha, Nebraska"
        places = search_places(query, max_pages=2)
        for place in places:
            inspected += 1
            details = get_place_details(place.get("place_id"))
            reviews = details.get("reviews", [])
            bad_recent = [
                r for r in reviews
                if r.get("rating", 5) <= REVIEW_CLUSTER_MAX_STARS
                and _review_time(r) >= cutoff
            ]
            if len(bad_recent) < REVIEW_CLUSTER_MIN_REVIEWS:
                continue
            company_name = details.get("name", place.get("name"))
            with __import__("sqlalchemy").orm.sessionmaker(bind=__import__("scraper.db_client", fromlist=["engine"]).engine)() as session:
                company = get_or_create_company(
                    session, company_name,
                    city="Omaha", state="Nebraska",
                    website=details.get("website"),
                    external_ids={"google_place_id": place.get("place_id")},
                )
                headline = f"{company_name} received {len(bad_recent)} reviews ≤2 stars in last 14 days"
                if __import__("scraper.db_client", fromlist=["signal_exists"]).signal_exists(session, company.id, SignalType.negative_review_cluster, headline):
                    skipped += 1
                    continue
                snippets = [f"- {r['rating']}★: {r.get('text','')[:120]}" for r in bad_recent[:5]]
                summary = "\n".join(snippets)
                sid = __import__("scraper.db_client", fromlist=["insert_signal"]).insert_signal(
                    company_id=company.id,
                    signal_type=SignalType.negative_review_cluster,
                    severity=min(5, 2 + len(bad_recent)),
                    headline=headline,
                    summary=summary,
                    source_url=details.get("url"),
                    source_api="google_places",
                    location_name=details.get("formatted_address"),
                    published_at=max(_review_time(r) for r in bad_recent),
                    metadata={
                        "bad_review_count": len(bad_recent),
                        "average_recent_rating": round(sum(r["rating"] for r in bad_recent) / len(bad_recent), 2),
                        "place_id": place.get("place_id"),
                    },
                )
                if sid:
                    created += 1

    return {"source": "google_reviews", "signals_created": created, "signals_skipped": skipped, "places_inspected": inspected}


def _review_time(review: dict) -> datetime:
    ts = review.get("time", 0)
    return datetime.utcfromtimestamp(ts)
