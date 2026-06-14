"""Apify business-license scraper placeholder.

Candidate actor: intelscrape/business-license-scraper
URL: https://apify.com/intelscrape/business-license-scraper

This actor can pull business-license records for a city/state/zip.  It is a
paid actor; wire it up once an Apify subscription or pay-per-result credit is
available.

Signal value: newly issued business licenses = brand-new companies to target
before competitors find them.
"""

from datetime import datetime

from scraper.config import APIFY_TOKEN
from scraper.db_client import Session
from app.models import SignalType


ACTOR_ID = "intelscrape/business-license-scraper"


def run(limit: int = 100) -> dict:
    if not APIFY_TOKEN:
        return {
            "source": "apify_business_licenses",
            "signals_created": 0,
            "status": "not_configured",
            "note": "Apify token not configured. Set APIFY_TOKEN in scraper/.env and subscribe to intelscrape/business-license-scraper.",
            "actor_url": f"https://apify.com/{ACTOR_ID}",
        }
    # TODO: use apify_client to run actor with input {"location": "Omaha, NE", "limit": limit}
    # then map each record to a SignalType.business_license signal.
    return {
        "source": "apify_business_licenses",
        "signals_created": 0,
        "status": "stub",
        "note": "Apify token present but actor integration not yet implemented.",
        "actor_url": f"https://apify.com/{ACTOR_ID}",
    }


if __name__ == "__main__":
    print(run())
