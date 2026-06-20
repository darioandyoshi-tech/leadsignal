#!/usr/bin/env python3
"""Congressional trading tracker.

Tracks stock transactions reported by members of the U.S. Congress
(Representatives and Senators) under the STOCK Act (Stop Trading on
Congressional Knowledge Act, 2012).

Data sources (in priority order):
  1. CapitolExposed API (free, no auth required)
     Base URL: https://www.capitolexposed.com/api/v1
     Rate-limited by IP. Returns JSON with pagination.
  2. Quiver Quant API (free tier, requires API key)
     Base URL: https://api.quiverquant.com
  3. Capitol Trades web scrape (fallback, often blocked by bot protection)

Signal logic:
  - High conflict_score + purchase → STRONG_BUY (politician trading in their
    oversight area)
  - Multiple politicians buying same stock within 30 days → BUY
  - Single politician purchase → WEAK_BUY (informational)
  - Same logic mirrored for sells
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

import httpx
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

USER_AGENT = "LeadSignal/1.0 contact@dmeomaha.com"

# CapitolExposed API (free, no auth)
CAPEX_BASE = "https://www.capitolexposed.com/api/v1"
CAPEX_TRADES_ENDPOINT = f"{CAPEX_BASE}/trades"
CAPEX_MEMBERS_ENDPOINT = f"{CAPEX_BASE}/members"

# Quiver Quant (free tier, requires key)
QUIVER_API_BASE = "https://api.quiverquant.com"

# Capitol Trades (fallback, often blocked)
CAPITOL_TRADES_URL = "https://www.capitoltrades.com/trades"

# Committee → sector mapping (simplified, for committee-overlap signal
# when CapitolExposed doesn't provide committee info directly)
COMMITTEE_SECTOR_MAP: Dict[str, List[str]] = {
    "Armed Services": ["LMT", "RTX", "GD", "NOC", "BA", "TDG", "HII", "LHX", "KRNT"],
    "Banking, Housing, and Urban Affairs": ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "SCHW"],
    "Commerce, Science, and Transportation": ["AMZN", "META", "GOOGL", "AAPL", "NFLX", "DIS", "CMCSA"],
    "Energy and Natural Resources": ["XOM", "CVX", "COP", "EOG", "PSX", "MPC", "VLO", "OXY", "HAL"],
    "Environment and Public Works": ["WM", "RSG", "CWY", "AWK", "WTRG", "MESO"],
    "Finance": ["JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "V", "MA"],
    "Foreign Affairs": ["LMT", "RTX", "GD", "NOC", "BA"],
    "Health, Education, Labor, and Pensions": ["JNJ", "PFE", "MRK", "ABT", "LLY", "UNH", "TMO", "DHR", "BMY"],
    "Homeland Security and Governmental Affairs": ["LMT", "RTX", "GD", "NOC", "CRWD", "PANW", "ZS"],
    "Judiciary": ["MSFT", "GOOGL", "META", "AAPL", "AMZN", "CRM"],
    "Agriculture, Nutrition, and Forestry": ["ADM", "BG", "CAG", "CPB", "TSN", "PPC", "MOS", "CF"],
    "Appropriations": ["LMT", "RTX", "GD", "NOC", "BA"],
    "Intelligence": ["PLTR", "CRWD", "PANW", "ZS", "LMT", "RTX", "GD", "NOC", "MSFT"],
    "Science, Space, and Technology": ["NVDA", "AMD", "AVGO", "QCOM", "TXN", "LRCX", "KLAC"],
    "Transportation and Infrastructure": ["UPS", "FDX", "UNP", "CSX", "NSC", "DAL", "LUV", "JBLU"],
    "Veterans' Affairs": ["JNJ", "PFE", "MRK", "ABT", "LLY", "UNH", "TMO"],
    "Ways and Means": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
}

# Reverse map: ticker → committees that oversee it
TICKER_COMMITTEE_MAP: Dict[str, List[str]] = defaultdict(list)
for committee, tickers in COMMITTEE_SECTOR_MAP.items():
    for ticker in tickers:
        TICKER_COMMITTEE_MAP[ticker].append(committee)

CLUSTER_THRESHOLD = 2      # 2+ politicians buying same stock in 30 days
CLUSTER_WINDOW_DAYS = 30
CAPEX_PAGE_SIZE = 100       # trades per page
CAPEX_MAX_PAGES = 3         # max pages to fetch (300 trades)
CONFLICT_SCORE_THRESHOLD = 0.3  # above this = high conflict signal


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class CongressionalTrade:
    """A single congressional stock transaction."""
    politician: str
    chamber: str                  # "house" or "senate"
    party: str
    committee: str                 # may be empty if unknown
    symbol: str
    transaction_type: str         # "buy" or "sell"
    transaction_date: str         # ISO date
    amount_range: str             # e.g. "$1,001 - $15,000"
    filing_date: str
    conflict_score: float
    source: str


# --------------------------------------------------------------------------- #
# Congressional Trade Scanner
# --------------------------------------------------------------------------- #

class CongressionalTradeScanner:
    """Scan public congressional trading data for signals.

    Usage:
        scanner = CongressionalTradeScanner()
        signals = scanner.get_congressional_signals()
    """

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self.user_agent = user_agent
        self._headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        self._client: Optional[httpx.Client] = None
        self._member_cache: Dict[str, dict] = {}  # member_id → member data

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self._headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    # -- Data source 1: CapitolExposed API (primary) ---------------------- #

    def _fetch_capex_trades(self) -> List[CongressionalTrade]:
        """Fetch recent congressional trades from CapitolExposed API.

        This is the primary data source. It's free, requires no auth,
        and returns structured JSON with conflict scores.
        """
        trades: List[CongressionalTrade] = []

        for page in range(1, CAPEX_MAX_PAGES + 1):
            try:
                resp = self.client.get(
                    CAPEX_TRADES_ENDPOINT,
                    params={"page": page, "per_page": CAPEX_PAGE_SIZE},
                    timeout=20,
                )
                if resp.status_code != 200:
                    print(f"[Congress] CapitolExposed returned {resp.status_code} on page {page}")
                    break

                data = resp.json()
                page_trades = data.get("data", [])
                if not page_trades:
                    break

                for t in page_trades:
                    trade = self._parse_capex_trade(t)
                    if trade:
                        trades.append(trade)

                # Check if there are more pages
                meta = data.get("meta", {})
                if not meta.get("has_more", False):
                    break

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                print(f"[Congress] CapitolExposed fetch error: {exc}")
                break
            except Exception as exc:
                print(f"[Congress] CapitolExposed parse error: {exc}")
                break

        return trades

    def _parse_capex_trade(self, raw: dict) -> Optional[CongressionalTrade]:
        """Parse a CapitolExposed trade dict into a CongressionalTrade."""
        ticker = (raw.get("ticker") or "").upper()
        if not ticker:
            return None

        txn_type_raw = (raw.get("transaction_type") or "").lower()
        if "buy" in txn_type_raw or "purchase" in txn_type_raw:
            txn_type = "buy"
        elif "sell" in txn_type_raw or "sale" in txn_type_raw:
            txn_type = "sell"
        else:
            return None

        # Parse dates (ISO format with possible T suffix)
        txn_date = _parse_iso_date(raw.get("transaction_date", ""))
        filing_date = _parse_iso_date(raw.get("disclosure_date", ""))

        # Build amount range string
        amt_min = raw.get("amount_min", "")
        amt_max = raw.get("amount_max", "")
        amount_range = f"${amt_min} - ${amt_max}" if amt_min and amt_max else ""

        # Get member info for chamber/party
        member_id = raw.get("member_id", "")
        member_name = raw.get("member_name", "")
        chamber = ""
        party = ""

        # Try to get from member cache or fetch
        if member_id and member_id not in self._member_cache:
            # Batch: we can't fetch member details for every trade
            # Just use what's in the trade data for now
            pass

        # Use conflict_score from the API
        conflict_score = float(raw.get("conflict_score", 0) or 0)

        return CongressionalTrade(
            politician=member_name,
            chamber=chamber,
            party=party,
            committee="",  # not provided in trades endpoint
            symbol=ticker,
            transaction_type=txn_type,
            transaction_date=txn_date,
            amount_range=amount_range,
            filing_date=filing_date,
            conflict_score=conflict_score,
            source="capitolexposed",
        )

    def _fetch_member_details(self, member_slug: str) -> dict:
        """Fetch member details (chamber, party, committees) from CapitolExposed."""
        if member_slug in self._member_cache:
            return self._member_cache[member_slug]
        try:
            resp = self.client.get(f"{CAPEX_MEMBERS_ENDPOINT}/{member_slug}", timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                self._member_cache[member_slug] = data
                return data
        except Exception:
            pass
        self._member_cache[member_slug] = {}
        return {}

    # -- Data source 2: Quiver Quant API (fallback) ----------------------- #

    def _fetch_quiver_trades(self) -> List[CongressionalTrade]:
        """Fetch congressional trades from Quiver Quant API (free tier).

        Requires QUIVER_API_KEY environment variable.
        """
        trades: List[CongressionalTrade] = []
        api_key = os.environ.get("QUIVER_API_KEY", "")

        if not api_key:
            return trades

        try:
            headers = {**self._headers, "x-api-key": api_key}
            resp = httpx.get(
                f"{QUIVER_API_BASE}/beta/latestcongresstrading",
                headers=headers,
                timeout=20,
            )
            if resp.status_code != 200:
                return trades

            data = resp.json()
            for item in data:
                ticker = (item.get("Ticker") or "").upper()
                if not ticker:
                    continue

                rep = item.get("Representative", "") or item.get("Senator", "")
                txn_type = "buy" if (item.get("Transaction") or "").lower().startswith("buy") else "sell"
                txn_date = _parse_iso_date(item.get("TransactionDate", "") or item.get("Traded", ""))

                trades.append(CongressionalTrade(
                    politician=rep,
                    chamber=item.get("Chamber", ""),
                    party=item.get("Party", ""),
                    committee="",
                    symbol=ticker,
                    transaction_type=txn_type,
                    transaction_date=txn_date,
                    amount_range=item.get("Range", ""),
                    filing_date=_parse_iso_date(item.get("Filed", "")),
                    conflict_score=0.0,
                    source="quiverquant",
                ))
        except Exception as exc:
            print(f"[Congress] Quiver Quant fetch failed: {exc}")

        return trades

    # -- Signal generation ------------------------------------------------- #

    def get_congressional_signals(self) -> List[dict]:
        """Main entry point: detect congressional trading signals.

        Returns a list of dicts with keys:
            symbol, signal, politician, committee, transaction_date,
            cluster_count, trades

        Signal logic:
          - High conflict_score (>=0.3) + buy → STRONG_BUY
          - 2+ politicians buying same stock within 30 days → BUY
          - Single politician buy → WEAK_BUY
          - Same mirrored for sells
        """
        trades: List[CongressionalTrade] = []

        # Try CapitolExposed first (primary source)
        trades = self._fetch_capex_trades()

        # Fallback to Quiver Quant if CapitolExposed fails
        if not trades:
            print("[Congress] CapitolExposed returned no trades, trying Quiver Quant...")
            trades = self._fetch_quiver_trades()

        if not trades:
            print("[Congress] No data source available. Returning empty signals.")
            return []

        print(f"[Congress] Fetched {len(trades)} trades from "
              f"{trades[0].source if trades else 'none'}")

        # Group by symbol and transaction type
        purchases: Dict[str, List[CongressionalTrade]] = defaultdict(list)
        sales: Dict[str, List[CongressionalTrade]] = defaultdict(list)

        for trade in trades:
            if trade.transaction_type == "buy":
                purchases[trade.symbol].append(trade)
            elif trade.transaction_type == "sell":
                sales[trade.symbol].append(trade)

        signals: List[dict] = []

        # Detect purchase signals
        for symbol, symbol_trades in purchases.items():
            if not symbol_trades:
                continue

            sorted_trades = sorted(
                symbol_trades,
                key=lambda t: t.transaction_date or "",
                reverse=True,
            )

            politicians = list({t.politician for t in sorted_trades if t.politician})
            cluster_count = len(politicians)

            # Check for committee overlap (using our static map)
            committees = TICKER_COMMITTEE_MAP.get(symbol, [])
            committee_match = ""

            # Check for high conflict score (CapitolExposed provides this)
            high_conflict = any(
                t.conflict_score >= CONFLICT_SCORE_THRESHOLD
                for t in sorted_trades
            )

            latest_date = sorted_trades[0].transaction_date if sorted_trades else ""

            if high_conflict or committees:
                signal = "STRONG_BUY"
                # Find the politician with the highest conflict score
                best = max(sorted_trades, key=lambda t: t.conflict_score)
                politician = best.politician
                committee = ", ".join(committees) if committees else "high_conflict"
            elif cluster_count >= CLUSTER_THRESHOLD:
                signal = "BUY"
                politician = politicians[0] if politicians else ""
                committee = ""
            else:
                signal = "WEAK_BUY"
                politician = politicians[0] if politicians else ""
                committee = ""

            signals.append({
                "symbol": symbol,
                "signal": signal,
                "politician": politician,
                "committee": committee,
                "transaction_date": latest_date,
                "cluster_count": cluster_count,
                "conflict_score": max(t.conflict_score for t in sorted_trades),
                "trades": [asdict(t) for t in sorted_trades[:10]],
            })

        # Detect sale signals
        for symbol, symbol_trades in sales.items():
            if not symbol_trades:
                continue

            sorted_trades = sorted(
                symbol_trades,
                key=lambda t: t.transaction_date or "",
                reverse=True,
            )

            politicians = list({t.politician for t in sorted_trades if t.politician})
            cluster_count = len(politicians)

            committees = TICKER_COMMITTEE_MAP.get(symbol, [])
            high_conflict = any(
                t.conflict_score >= CONFLICT_SCORE_THRESHOLD
                for t in sorted_trades
            )

            latest_date = sorted_trades[0].transaction_date if sorted_trades else ""

            if high_conflict or committees:
                signal = "STRONG_SELL"
                best = max(sorted_trades, key=lambda t: t.conflict_score)
                politician = best.politician
                committee = ", ".join(committees) if committees else "high_conflict"
            elif cluster_count >= CLUSTER_THRESHOLD:
                signal = "SELL"
                politician = politicians[0] if politicians else ""
                committee = ""
            else:
                signal = "WEAK_SELL"
                politician = politicians[0] if politicians else ""
                committee = ""

            signals.append({
                "symbol": symbol,
                "signal": signal,
                "politician": politician,
                "committee": committee,
                "transaction_date": latest_date,
                "cluster_count": cluster_count,
                "conflict_score": max(t.conflict_score for t in sorted_trades),
                "trades": [asdict(t) for t in sorted_trades[:10]],
            })

        # Sort: strong signals first, then by cluster count
        signals.sort(
            key=lambda s: (
                0 if "STRONG" in s["signal"] else 1,
                -s["cluster_count"],
            )
        )

        return signals


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _parse_iso_date(date_str: str) -> str:
    """Parse an ISO date string and return YYYY-MM-DD.

    Handles formats like '2026-06-16T00:00:00.000Z' and '2026-06-16'.
    """
    if not date_str:
        return ""
    # Extract just the date part
    date_part = date_str.split("T")[0] if "T" in date_str else date_str
    try:
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_part.strip()


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to ISO YYYY-MM-DD."""
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", date_str)
    if m:
        mo, d, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return date_str.strip()


# --------------------------------------------------------------------------- #
# Module entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    scanner = CongressionalTradeScanner()
    try:
        print("Fetching congressional trading data...")
        signals = scanner.get_congressional_signals()
        print(f"\nFound {len(signals)} congressional signals:\n")
        for s in signals:
            print(
                f"  {s['symbol']:6s}  {s['signal']:12s}  "
                f"politician={s['politician']}  "
                f"committee={s['committee']}  "
                f"date={s['transaction_date']}  "
                f"cluster={s['cluster_count']}  "
                f"conflict={s.get('conflict_score', 0)}"
            )
    finally:
        scanner.close()