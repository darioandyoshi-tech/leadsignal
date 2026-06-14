
"""Indeed RSS / HTML scraping for Omaha job postings."""

import re
import uuid
import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup
from scraper.config import OMAHA, HIRING_SPIKE_MIN_NEW_JOBS
from scraper.db_client import get_or_create_company, insert_signal
from app.models import SignalType


BASE_RSS = "https://rss.indeed.com/rss"
SEARCH_BASE = "https://www.indeed.com/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_rss_jobs(query: str, location: str = "Omaha, NE", max_results: int = 50) -> list:
    q = urlencode({"q": query, "l": location, "fromage": "7"})
    url = f"{BASE_RSS}?{q}"
    feed = feedparser.parse(url)
    jobs = []
    for entry in feed.entries[:max_results]:
        jobs.append({
            "title": entry.get("title", ""),
            "company": _clean_company(entry.get("author", "")),
            "link": entry.get("link", ""),
            "published": _parse_date(entry.get("published", "")),
            "summary": entry.get("summary", ""),
        })
    return jobs


def fetch_html_jobs(query: str, location: str = "Omaha, NE", start: int = 0) -> list:
    params = {"q": query, "l": location, "fromage": "7", "start": start}
    url = f"{SEARCH_BASE}?{urlencode(params)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)
    jobs = []
    for card in cards:
        title_tag = card.find("h2", class_="jobTitle")
        company_tag = card.find("span", attrs={"data-testid": "company-name"})
        summary_tag = card.find("div", class_="job-snippet")
        link_tag = title_tag.find("a") if title_tag else None
        jobs.append({
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "company": _clean_company(company_tag.get_text(strip=True)) if company_tag else "",
            "link": f"https://www.indeed.com{link_tag['href']}" if link_tag and link_tag.has_attr("href") else "",
            "published": datetime.utcnow(),
            "summary": summary_tag.get_text(strip=True) if summary_tag else "",
        })
    return jobs


def _clean_company(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = re.sub(r"[-–]\s*\d+.*reviews", "", raw, flags=re.I)
    return raw


def _parse_date(s: str) -> datetime:
    try:
        return datetime(*feedparser._parse_date(s)[:6])
    except Exception:
        return datetime.utcnow() - timedelta(days=1)


def run() -> dict:
    """Collect jobs from Indeed and emit hiring-spike signals."""
    all_jobs = []
    for keyword in [""]:  # broad "Omaha" search; narrow by industry later
        all_jobs.extend(fetch_rss_jobs(keyword))

    # Bucket by company (last 7 days)
    cutoff = datetime.utcnow() - timedelta(days=7)
    by_company = {}
    for job in all_jobs:
        if not job.get("company") or job.get("published", datetime.utcnow()) < cutoff:
            continue
        by_company.setdefault(job["company"], []).append(job)

    created = 0
    skipped = 0
    for company_name, jobs in by_company.items():
        if len(jobs) < HIRING_SPIKE_MIN_NEW_JOBS:
            continue
        with __import__("sqlalchemy").orm.sessionmaker(bind=__import__("scraper.db_client", fromlist=["engine"]).engine)() as session:
            company = get_or_create_company(session, company_name, city="Omaha", state="Nebraska")
            headline = f"{company_name} posted {len(jobs)} jobs in Omaha area this week"
            if __import__("scraper.db_client", fromlist=["signal_exists"]).signal_exists(session, company.id, SignalType.hiring_spike, headline):
                skipped += 1
                continue
            job_links = [f"- {j['title']}: {j['link']}" for j in jobs[:5]]
            summary = "\n".join(job_links)
            sid = __import__("scraper.db_client", fromlist=["insert_signal"]).insert_signal(
                company_id=company.id,
                signal_type=SignalType.hiring_spike,
                severity=min(5, 2 + len(jobs) // 2),
                headline=headline,
                summary=summary,
                source_url=jobs[0]["link"],
                source_api="indeed",
                location_name="Omaha, NE",
                published_at=max(j.get("published", datetime.utcnow()) for j in jobs),
                metadata={"job_count": len(jobs), "titles": [j["title"] for j in jobs[:10]]},
            )
            if sid:
                created += 1

    return {"source": "indeed", "signals_created": created, "signals_skipped": skipped, "jobs_collected": len(all_jobs)}
