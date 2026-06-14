"""Sarpy County SmartGov public portal scraper (best-effort).

URL: https://co-sarpy-ne.smartgovcommunity.com/Public/Home
SmartGov is a Citizenserve product.  Public users can search permits,
inspections, code cases, and contractors without a login, but detail data
is behind an interactive form.

Signal value: live Sarpy County building/contractor/inspection activity.
"""

import httpx
from datetime import datetime
from typing import List, Dict

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


HOME_URL = "https://co-sarpy-ne.smartgovcommunity.com/Public/Home"


def _home_reachable() -> bool:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            r = client.get(HOME_URL, headers={"User-Agent": "Mozilla/5.0"})
            return r.status_code < 500
    except Exception:
        return False


def run(limit: int = 50) -> dict:
    if not _home_reachable():
        return {
            "source": "sarpy_smartgov",
            "signals_created": 0,
            "status": "error",
            "note": "SmartGov portal is not reachable or requires a browser session. Use browser automation (Playwright/Selenium) or an Apify actor for Citizenserve portals.",
        }
    return {
        "source": "sarpy_smartgov",
        "signals_created": 0,
        "status": "placeholder",
        "note": "Portal reachable, but permit search endpoints require JavaScript session state. Implement Playwright/Apify actor to extract permit/inspection results.",
    }


if __name__ == "__main__":
    print(run())
