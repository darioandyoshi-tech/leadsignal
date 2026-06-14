"""Apify-based scrapers for job and review signals.

Uses the verified actors:
  - borderline/indeed-scraper for Omaha-area jobs
  - compass/Google-Maps-Reviews-Scraper for business reviews

Requires APIFY_TOKEN env var.
"""

import os
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional

try:
    from apify_client import ApifyClient
except ImportError:  # pragma: no cover
    ApifyClient = None

from scraper.config import (
    OMAHA,
    TARGET_INDUSTRIES,
    HIRING_SPIKE_WINDOW_DAYS,
    HIRING_SPIKE_MIN_NEW_JOBS,
    REVIEW_CLUSTER_MIN_REVIEWS,
    REVIEW_CLUSTER_MAX_STARS,
)
from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from backend.app.models import SignalType


APIFY_TOKEN = os.getenv("APIFY_TOKEN")


def _client() -> Optional["ApifyClient"]:
    if not APIFY_TOKEN or ApifyClient is None:
        return None
    return ApifyClient(APIFY_TOKEN)


def _run_actor_sync(
    actor_name: str,
    input_payload: dict,
    timeout_secs: int = 120,
    max_items: int = 100,
) -> List[dict]:
    client = _client()
    if client is None:
        return []
    try:
        run = client.actor(actor_name).call(
            run_input=input_payload,
            timeout_secs=timeout_secs,
            memory_mbytes=4096,
        )
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        items = []
        for item in client.dataset(dataset_id).iterate_items():
            items.append(item)
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"Apify actor {actor_name} error: {e}")
        return []


# ---------------------------------------------------------------------------
# Indeed jobs
# ---------------------------------------------------------------------------


def fetch_indeed_jobs(
    position: str = "",
    location: str = "Omaha, NE",
    days: int = 7,
    max_items: int = 100,
) -> List[dict]:
    """Fetch recent Omaha-area jobs from Apify Indeed scraper."""
    actor_name = "borderline/indeed-scraper"
    input_payload = {
        "position": position,
        "location": location,
        "country": "US",
        "maxItems": max_items,
        "parseCompanyDetails": False,
    }
    return _run_actor_sync(actor_name, input_payload, timeout_secs=180, max_items=max_items)


def run_indeed() -> dict:
    """Collect Omaha-area jobs and emit hiring-spike signals."""
    keywords = [""] + TARGET_INDUSTRIES[:5]
    all_jobs = []
    for kw in keywords:
        jobs = fetch_indeed_jobs(position=kw, max_items=50)
        for j in jobs:
            j["_search_keyword"] = kw
        all_jobs.extend(jobs)

    cutoff = datetime.utcnow() - timedelta(days=HIRING_SPIKE_WINDOW_DAYS)
    by_company: dict[str, list] = {}
    for job in all_jobs:
        company = _clean_company(job.get("companyName") or job.get("company") or "Unknown")
        if not company:
            continue
        posted = _parse_iso(job.get("postedAt") or job.get("date"))
        if posted and posted < cutoff:
            continue
        by_company.setdefault(company, []).append(job)

    created = 0
    skipped = 0
    for company_name, jobs in by_company.items():
        if len(jobs) < HIRING_SPIKE_MIN_NEW_JOBS:
            continue
        with Session() as session:
            company = get_or_create_company(session, company_name, city="Omaha", state="Nebraska")
            headline = f"{company_name} posted {len(jobs)} jobs in Omaha area this week"
            if signal_exists(session, company.id, SignalType.hiring_spike, headline):
                skipped += 1
                continue
            job_links = [
                f"- {j.get('title', j.get('positionName', 'Job'))}: {j.get('url', j.get('detailUrl', ''))}"
                for j in jobs[:5]
            ]
            published_ats = [_parse_iso(j.get("postedAt") or j.get("date")) for j in jobs]
            published_at = max([dt for dt in published_ats if dt], default=None)
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.hiring_spike,
                severity=min(5, 2 + len(jobs) // 2),
                headline=headline,
                summary="\n".join(job_links),
                source_url=jobs[0].get("url", jobs[0].get("detailUrl", "https://www.indeed.com")),
                source_api="apify_indeed",
                location_name="Omaha, NE",
                published_at=published_at,
                metadata={
                    "job_count": len(jobs),
                    "titles": [j.get("title", j.get("positionName", "")) for j in jobs[:10]],
                    "search_keywords": list(set(j.get("_search_keyword", "") for j in jobs)),
                },
            )
            if sid:
                created += 1

    return {
        "source": "apify_indeed",
        "signals_created": created,
        "signals_skipped": skipped,
        "jobs_collected": len(all_jobs),
    }


# ---------------------------------------------------------------------------
# Google Maps reviews
# ---------------------------------------------------------------------------


def fetch_google_reviews(
    place_id: Optional[str] = None,
    search_query: Optional[str] = None,
    max_reviews: int = 50,
) -> List[dict]:
    """Fetch reviews for a place or search query via Apify Google Maps Reviews Scraper."""
    actor_name = "compass/Google-Maps-Reviews-Scraper"
    input_payload = {"maxReviews": max_reviews, "reviewsSort": "newest"}
    if place_id:
        input_payload["placeIds"] = [place_id]
    elif search_query:
        input_payload["searchStringsArray"] = [search_query]
    else:
        return []
    return _run_actor_sync(actor_name, input_payload, timeout_secs=180, max_items=max_reviews)


def run_google_reviews() -> dict:
    """Collect negative review clusters for Omaha businesses."""
    created = 0
    skipped = 0
    inspected = 0
    cutoff = datetime.utcnow() - timedelta(days=14)

    for industry in TARGET_INDUSTRIES[:8]:
        query = f"{industry} in Omaha, Nebraska"
        places = fetch_google_reviews(search_query=query, max_reviews=20)
        for place in places:
            inspected += 1
            reviews = place.get("reviews", []) or place.get("reviewsData", {}).get("reviews", [])
            company_name = place.get("title") or place.get("name") or "Unknown Business"
            place_id = place.get("placeId") or place.get("place_id")
            address = place.get("address") or place.get("formattedAddress")

            bad_recent = [
                r
                for r in reviews
                if _review_rating(r) <= REVIEW_CLUSTER_MAX_STARS and _review_time(r) >= cutoff
            ]
            if len(bad_recent) < REVIEW_CLUSTER_MIN_REVIEWS:
                continue

            with Session() as session:
                company = get_or_create_company(
                    session,
                    company_name,
                    city="Omaha",
                    state="Nebraska",
                    website=place.get("website"),
                    external_ids={"google_place_id": place_id} if place_id else {},
                )
                headline = f"{company_name} received {len(bad_recent)} reviews ≤2 stars in last 14 days"
                if signal_exists(session, company.id, SignalType.negative_review_cluster, headline):
                    skipped += 1
                    continue
                snippets = [
                    f"- {r['stars']}★: {r.get('text', '')[:120]}" for r in bad_recent[:5]
                ]
                published_at = max(_review_time(r) for r in bad_recent)
                sid = insert_signal(
                    company_id=company.id,
                    signal_type=SignalType.negative_review_cluster,
                    severity=min(5, 2 + len(bad_recent)),
                    headline=headline,
                    summary="\n".join(snippets),
                    source_url=place.get("url") or place.get("reviewUrl"),
                    source_api="apify_google_reviews",
                    location_name=address,
                    published_at=published_at,
                    metadata={
                        "bad_review_count": len(bad_recent),
                        "average_recent_rating": round(
                            sum(_review_rating(r) for r in bad_recent) / len(bad_recent), 2
                        ),
                        "place_id": place_id,
                    },
                )
                if sid:
                    created += 1

    return {
        "source": "apify_google_reviews",
        "signals_created": created,
        "signals_skipped": skipped,
        "places_inspected": inspected,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_company(raw: str) -> str:
    if not raw:
        return ""
    raw = str(raw).strip()
    raw = re.sub(r"\s*[-–]\s*\d+.*reviews?", "", raw, flags=re.I)
    return raw


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def _review_rating(review: dict) -> float:
    return float(review.get("stars") or review.get("rating") or 5)


def _review_time(review: dict) -> datetime:
    ts = review.get("publishAt") or review.get("publishedAtDate") or review.get("timestamp")
    dt = _parse_iso(ts) if isinstance(ts, str) else None
    return dt or datetime.utcnow()


def run() -> dict:
    """Run both Apify-powered sources."""
    if not APIFY_TOKEN or ApifyClient is None:
        return {"source": "apify", "error": "Apify not configured", "signals_created": 0}
    indeed_result = run_indeed()
    reviews_result = run_google_reviews()
    return {
        "source": "apify",
        "signals_created": indeed_result.get("signals_created", 0)
        + reviews_result.get("signals_created", 0),
        "indeed": indeed_result,
        "google_reviews": reviews_result,
    }


if __name__ == "__main__":
    print(run())
