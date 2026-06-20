"""Fetch news headlines for stocks.

Primary source: yfinance ``ticker.news``.
Fallback: Google News RSS feed.

Rate limited to 1 request per second to avoid getting throttled.
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List
from urllib.parse import quote_plus

import httpx
import yfinance as yf

logger = logging.getLogger(__name__)

# Rate limiter — shared across all fetcher instances
_last_request_time: Dict[str, float] = {}
_MIN_INTERVAL = 1.0  # seconds between requests to the same source


class NewsFetcher:
    """Fetch news headlines for a given stock symbol.

    Tries yfinance first (``ticker.news``), falls back to Google News RSS
    if yfinance returns nothing.
    """

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._cache: Dict[str, tuple] = {}  # symbol -> (headlines, timestamp)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    def _rate_limit(self, source: str) -> None:
        now = time.monotonic()
        last = _last_request_time.get(source, 0.0)
        elapsed = now - last
        if elapsed < self._min_interval:
            sleep_for = self._min_interval - elapsed
            logger.debug("Rate limit: sleeping %.2fs for %s", sleep_for, source)
            time.sleep(sleep_for)
        _last_request_time[source] = time.monotonic()

    # ------------------------------------------------------------------
    # yfinance
    # ------------------------------------------------------------------
    def _fetch_yfinance(self, symbol: str, limit: int) -> List[str]:
        try:
            self._rate_limit("yfinance")
            ticker = yf.Ticker(symbol)
            news = ticker.news
            if not news:
                return []

            headlines: List[str] = []
            for item in news[:limit]:
                # yfinance news items have different shapes across versions
                title = None
                if isinstance(item, dict):
                    title = item.get("title") or item.get("headline")
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    # Some yfinance versions return tuples
                    title = item[0] if isinstance(item[0], str) else None
                if title:
                    headlines.append(str(title).strip())
            return headlines
        except Exception as exc:
            logger.warning("yfinance news fetch failed for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # Google News RSS fallback
    # ------------------------------------------------------------------
    def _fetch_google_news(self, symbol: str, limit: int) -> List[str]:
        try:
            self._rate_limit("google_news")
            # Use the ticker + company name hint
            query = quote_plus(f"{symbol} stock")
            url = self.GOOGLE_NEWS_RSS.format(query=query)

            resp = httpx.get(url, timeout=15, headers={"User-Agent": "LeadSignal/1.0"})
            if resp.status_code != 200:
                logger.warning("Google News RSS returned %d for %s", resp.status_code, symbol)
                return []

            root = ET.fromstring(resp.text)
            headlines: List[str] = []
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    # Clean HTML entities from Google News titles
                    title = title_elem.text.strip()
                    title = re.sub(r" - [A-Z][A-Za-z\s]+$", "", title)  # strip " - Source Name"
                    headlines.append(title)
                    if len(headlines) >= limit:
                        break
            return headlines
        except Exception as exc:
            logger.warning("Google News RSS failed for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_headlines(self, symbol: str, limit: int = 10) -> List[str]:
        """Fetch up to *limit* news headlines for *symbol*.

        Tries yfinance first, falls back to Google News RSS.
        Results are cached for 1 hour per symbol.
        """
        symbol = symbol.upper()
        cache_key = symbol
        now = time.time()

        # Check cache (1 hour TTL)
        if cache_key in self._cache:
            headlines, cached_at = self._cache[cache_key]
            if now - cached_at < 3600:
                logger.debug("Using cached headlines for %s", symbol)
                return headlines

        # Try yfinance first
        headlines = self._fetch_yfinance(symbol, limit)

        # Fallback to Google News RSS
        if not headlines:
            logger.debug("yfinance returned no headlines for %s, trying Google News", symbol)
            headlines = self._fetch_google_news(symbol, limit)

        if not headlines:
            logger.info("No headlines found for %s", symbol)

        self._cache[cache_key] = (headlines, now)
        return headlines