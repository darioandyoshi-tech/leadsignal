"""City of Omaha Accela Citizen Access live permit scraper.

URL: https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx
Accela is a JS-heavy ASP.NET portal.  We use Playwright to fill the search
form and extract the results grid.  This module requires a browser runtime
(Chromium) and the `playwright` Python package.

Signal value: live City of Omaha building/electrical/plumbing/mechanical/wreck
permits with project description, address, and contractor.
"""

import os
import re
from datetime import datetime, timedelta
from typing import List, Dict

from scraper.db_client import get_or_create_company, insert_signal, Session, signal_exists
from app.models import SignalType


HOME_URL = "https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx"
DEFAULT_SEARCH_URL = "https://aca-prod.accela.com/OMAHA/Cap/CapSearch.aspx?module=Building"


def _extract_table_rows(page_source: str) -> List[Dict]:
    """Parse the Accela search result grid from rendered HTML."""
    rows = []
    # Accela renders each result row with a CapID hidden input + visible cells.
    # We'll use a broad regex to pull blocks and fall back to BeautifulSoup if installed.
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page_source, "lxml")
        table = soup.select_one("table[id*='gvPermitList']")
        if not table:
            return rows
        for tr in table.find_all("tr")[1:]:  # skip header row
            if len(tds) < 4:
                continue
            texts = [td.get_text(strip=True) for td in tds]
            rows.append({
                "permit_number": texts[0] if len(texts) > 0 else "N/A",
                "project": texts[1] if len(texts) > 1 else "",
                "address": texts[2] if len(texts) > 2 else "",
                "status": texts[3] if len(texts) > 3 else "",
            })
    except Exception:
        pass
    return rows


def _run_playwright_search(limit: int = 50) -> List[Dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    rows = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64)")
            page = context.new_page()
            try:
                page.goto(HOME_URL, wait_until="networkidle", timeout=60000)
                # Accept disclaimer if present.
                try:
                    page.click("input[id*='btnAccept']", timeout=5000)
                except Exception:
                    pass
                # Navigate to the search module.
                page.goto(DEFAULT_SEARCH_URL, wait_until="networkidle", timeout=60000)

                # Accela search form: try to set date range to last 30 days and search.
                try:
                    from_field = page.locator("input[id*='txtFrom']")
                    to_field = page.locator("input[id*='txtTo']")
                    if from_field.count():
                        from_field.fill((datetime.now() - timedelta(days=30)).strftime("%m/%d/%Y"))
                    if to_field.count():
                        to_field.fill(datetime.now().strftime("%m/%d/%Y"))
                    page.click("input[id*='btnSearch']", timeout=10000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass

                # Wait for results grid.
                try:
                    page.wait_for_selector("table[id*='gvPermitList']", timeout=30000)
                except Exception:
                    pass

                rows = _extract_table_rows(page.content())[:limit]
            finally:
                context.close()
                browser.close()
    except Exception as e:
        print(f"Accela Playwright error: {e}")
        return []
    return rows


def _seed_fallback(limit: int = 50) -> List[Dict]:
    """Fallback seed data when Playwright is unavailable or the portal blocks."""
    return [
        {
            "permit_number": f"ACC-2026-{i:05d}",
            "project": "Sample Accela permit project",
            "address": "123 Example St, Omaha, NE",
            "status": "Issued",
        }
        for i in range(limit)
    ]


def run(limit: int = 50) -> dict:
    rows = _run_playwright_search(limit)
    live_fetch = bool(rows)

    if not rows:
        # Don't seed fake placeholder data in production.
        return {
            "source": "accela_omaha",
            "signals_created": 0,
            "signals_skipped": 0,
            "rows_processed": 0,
            "live_fetch": live_fetch,
            "note": "No rows extracted from Accela portal",
        }

    created = 0
    skipped = 0
    for item in rows:
        permit_number = item.get("permit_number", "N/A")
        address = item.get("address", "")
        project = item.get("project", "")

        with Session() as session:
            company = get_or_create_company(
                session, "Unknown Contractor", city="Omaha", state="NE"
            )
            headline = f"Omaha permit {permit_number}: {project[:80]}"
            if signal_exists(session, company.id, SignalType.permit_filing, headline):
                skipped += 1
                continue
            sid = insert_signal(
                company_id=company.id,
                signal_type=SignalType.permit_filing,
                severity=2,
                headline=headline,
                summary=f"Address: {address}\nStatus: {item.get('status', 'N/A')}\nProject: {project}",
                source_url=HOME_URL,
                source_api="accela_omaha",
                location_name=address,
                published_at=datetime.now(),
                metadata={
                    "permit_number": permit_number,
                    "address": address,
                    "project": project,
                    "status": item.get("status", ""),
                    "live_fetch": live_fetch,
                },
                session=session,
            )
            if sid:
                created += 1
            session.commit()

    return {
        "source": "accela_omaha",
        "signals_created": created,
        "signals_skipped": skipped,
        "rows_processed": len(rows),
        "live_fetch": live_fetch,
    }


if __name__ == "__main__":
    print(run())
