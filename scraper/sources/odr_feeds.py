"""ODR RSS feed parsers and public-notice scrapers.

ODR repackages public notices from City of Omaha, Douglas County, school
districts, and other entities. Its RSS feeds are public and machine-readable,
so we use them for signal discovery and link each item back to the official
publisher when possible.
"""

import feedparser
import re
import requests
from datetime import datetime
from typing import List

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


# Verified live ODR RSS feeds (discovered by scraping the ODR site map).
FEED_URLS = {
    "building_permits": "https://www.omahadailyrecord.com/taxonomy/term/3701/all/feed",
    "mechanical_permits": "https://www.omahadailyrecord.com/taxonomy/term/3807/all/feed",
    "electrical_permits": "https://www.omahadailyrecord.com/taxonomy/term/3702/all/feed",
    "plumbing_permits": "https://www.omahadailyrecord.com/taxonomy/term/3704/all/feed",
    "wreck_permits": "https://www.omahadailyrecord.com/taxonomy/term/3735/all/feed",
    "citycounty_bids": "https://www.omahadailyrecord.com/taxonomy/term/3706/all/feed",
    "public_notices": "https://www.omahadailyrecord.com/taxonomy/term/3692/all/feed",
    "real_estate_leads": "https://www.omahadailyrecord.com/taxonomy/term/3703/all/feed",
    "notice_of_default": "https://www.omahadailyrecord.com/taxonomy/term/3766/all/feed",
    "deeds": "https://www.omahadailyrecord.com/taxonomy/term/3719/all/feed",
    "active_property_sales": "https://www.omahadailyrecord.com/taxonomy/term/3700/all/feed",
    "active_probates": "https://www.omahadailyrecord.com/taxonomy/term/3718/all/feed",
    "tax_lien": "https://www.omahadailyrecord.com/taxonomy/term/3806/all/feed",
    "city_omaha": "https://www.omahadailyrecord.com/taxonomy/term/3694/all/feed",
    "douglas_county": "https://www.omahadailyrecord.com/taxonomy/term/3695/all/feed",
    "sarpy_county": "https://www.omahadailyrecord.com/taxonomy/term/3746/all/feed",
    "state_nebraska": "https://www.omahadailyrecord.com/taxonomy/term/3693/all/feed",
    "omaha_public_schools": "https://www.omahadailyrecord.com/taxonomy/term/3696/all/feed",
    "millard_public_schools": "https://www.omahadailyrecord.com/taxonomy/term/3748/all/feed",
    "westside_community_schools": "https://www.omahadailyrecord.com/taxonomy/term/3753/all/feed",
    "bennington_public_schools": "https://www.omahadailyrecord.com/taxonomy/term/3756/all/feed",
    "omaha_airport_authority": "https://www.omahadailyrecord.com/taxonomy/term/3827/all/feed",
    "omaha_housing_authority": "https://www.omahadailyrecord.com/taxonomy/term/3826/all/feed",
    "meca": "https://www.omahadailyrecord.com/taxonomy/term/3747/all/feed",
    "mapa": "https://www.omahadailyrecord.com/taxonomy/term/3749/all/feed",
    "learning_community": "https://www.omahadailyrecord.com/taxonomy/term/3750/all/feed",
    "metro_transit_authority": "https://www.omahadailyrecord.com/taxonomy/term/3829/all/feed",
    "public_records": "https://www.omahadailyrecord.com/taxonomy/term/3698/all/feed",
}


def _fetch_feed(url: str) -> List[dict]:
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return []
    parsed = feedparser.parse(r.text)
    return [
        {
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "published": entry.get("published_parsed") or entry.get("updated_parsed"),
            "summary": entry.get("summary", "").strip(),
        }
        for entry in parsed.get("entries", [])
    ]


def _pubdate_to_datetime(published) -> datetime | None:
    if not published:
        return None
    try:
        return datetime(*published[:6])
    except Exception:
        return None


def _signal_type_for_feed(feed_name: str) -> SignalType:
    if "permit" in feed_name:
        return SignalType.permit_filing
    if feed_name in ("notice_of_default", "active_property_sales", "tax_lien"):
        return SignalType.tax_delinquency
    if feed_name == "deeds":
        return SignalType.parcel_change
    if feed_name == "active_probates":
        return SignalType.new_business_registration
    if feed_name in ("citycounty_bids", "city_omaha", "douglas_county", "sarpy_county", "state_nebraska"):
        return SignalType.gov_contract_award
    return SignalType.new_business_registration


def _is_omaha_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(x in text for x in ["omaha", "douglas", "sarpy", "bellevue", "ralston", "gretna", "bennington", "valley", "waterloo", "boys town", "nebraska"])


def _classify_public_notice(title: str, summary: str) -> SignalType:
    """Classify a public notice article by content keywords."""
    text = f"{title} {summary}".lower()
    # Strip common HTML tags so keywords inside the body are visible.
    for tag in ["<p>", "</p>", "<strong>", "</strong>", "<em>", "</em>", "<div>", "</div>", "<span>", "</span>", "<br>", "<br/>", "\n"]:
        text = text.replace(tag, " ")
    text = re.sub(r"<[^>]+>", " ", text)

    if any(k in text for k in ["liquor license", "class c license", "alcoholic liquor", "beverage control"]):
        return SignalType.business_license
    if any(k in text for k in ["bid", "rfp", "request for proposal", "invitation to bid", "solicitation", "contract award", "notice inviting bids", "sealed bids"]):
        return SignalType.gov_contract_award
    if any(k in text for k in ["probate", "estate of", "notice to creditors"]):
        return SignalType.new_business_registration
    if any(k in text for k in ["tax sale", "delinquent tax", "property sale", "foreclosure", "tax lien"]):
        return SignalType.tax_delinquency
    if any(k in text for k in ["deed", "quit claim", "warranty deed", "trustee deed"]):
        return SignalType.parcel_change
    return SignalType.new_business_registration


def _extract_organization(title: str) -> str:
    """Best-effort publisher name from ODR notice title."""
    title = title.replace("Public Notices", "").replace("Notice Inviting Bids", "").strip(" -")
    if not title:
        return "Unknown Publisher"
    return title.strip()


def run(limit_per_feed: int = 50) -> dict:
    created = 0
    skipped = 0
    inspected = 0
    by_type = {}

    for feed_name, url in FEED_URLS.items():
        entries = _fetch_feed(url)[:limit_per_feed]
        signal_type = _signal_type_for_feed(feed_name)
        for entry in entries:
            inspected += 1
            title = entry["title"]
            summary = entry["summary"]
            if not _is_omaha_relevant(title, summary):
                continue
            # Public notices can cover many topics; classify by content.
            if feed_name == "public_notices":
                signal_type = _classify_public_notice(title, summary)
            company_name = _extract_organization(title)
            published_at = _pubdate_to_datetime(entry["published"])

            with Session() as session:
                company = get_or_create_company(
                    session, company_name, city="Omaha", state="Nebraska"
                )
                headline = f"[{feed_name.replace('_', ' ')}] {title[:180]}"
                if signal_exists(session, company.id, signal_type, headline):
                    skipped += 1
                    continue
                sid = insert_signal(
                    company_id=company.id,
                    signal_type=signal_type,
                    severity=2,
                    headline=headline,
                    summary=summary or title,
                    source_url=entry["link"] or url,
                    source_api=f"odr_{feed_name}",
                    location_name="Omaha, NE",
                    published_at=published_at,
                    metadata={
                        "feed": feed_name,
                        "feed_url": url,
                        "article_url": entry["link"],
                    },
                    session=session,
                )
                if sid:
                    created += 1
                    by_type[signal_type.value] = by_type.get(signal_type.value, 0) + 1
                session.commit()

    return {
        "source": "odr_feeds",
        "signals_created": created,
        "signals_skipped": skipped,
        "entries_inspected": inspected,
        "by_type": by_type,
    }


if __name__ == "__main__":
    print(run())
