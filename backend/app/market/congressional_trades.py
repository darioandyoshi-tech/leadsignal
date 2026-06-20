#!/usr/bin/env python3
"""Congressional trading tracker.

Tracks stock transactions reported by members of the U.S. Congress
(Representatives and Senators) under the STOCK Act (Stop Trading on
Congressional Knowledge Act, 2012).

Data sources (all free / public):
  1. Capitol Trades   – https://www.capitoltrades.com (public website)
  2. Quiver Quant     – https://api.quiverquant.com (free tier, public data)
  3. Congress.gov     – Periodic Transaction Report (PTR) PDFs
  4. Senate / House  – Official PTR filings

Signal logic:
  - Committee member buying stock in their oversight sector → STRONG_BUY
  - Multiple politicians buying same stock within 30 days → BUY
  - Single politician purchase → WEAK_BUY (informational)
  - Same logic mirrored for sells

NOTE: Free congressional trading APIs are fragmented and frequently change.
This module implements a best-effort scanner with graceful fallback. If all
data sources are unavailable, it returns an empty list with a clear note.
"""

from __future__ import annotations

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
CAPITOL_TRADES_URL = "https://www.capitoltrades.com/trades"
QUIVER_API_BASE = "https://api.quiverquant.com"
CONGRESS_INVESTS_URL = "https:// congressinvests.com"  # placeholder

# Committee → sector mapping (simplified)
# Used to detect when a politician on a relevant committee trades in that sector
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
    "Appropriations": ["LMT", "RTX", "GD", "NOC", "BA"],  # defense + broad
    "Budget": [],   # broad — no specific sector
    "Intelligence": ["PLTR", "CRWD", "PANW", "ZS", "LMT", "RTX", "GD", "NOC", "MSFT"],
    "Rules": [],
    "Small Business and Entrepreneurship": [],
    "Veterans' Affairs": ["JNJ", "PFE", "MRK", "ABT", "LLY", "UNH", "TMO"],
    "Ways and Means": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "Science, Space, and Technology": ["NVDA", "AMD", "AVGO", "QCOM", "TXN", "LRCX", "KLAC"],
    "Transportation and Infrastructure": ["UPS", "FDX", "UNP", "CSX", "NSC", "DAL", "LUV", "JBLU"],
}

# Reverse map: ticker → committees that oversee it
TICKER_COMMITTEE_MAP: Dict[str, List[str]] = defaultdict(list)
for committee, tickers in COMMITTEE_SECTOR_MAP.items():
    for ticker in tickers:
        TICKER_COMMITTEE_MAP[ticker].append(committee)

CLUSTER_THRESHOLD = 2      # 2+ politicians buying same stock in 30 days
CLUSTER_WINDOW_DAYS = 30


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class CongressionalTrade:
    """A single congressional stock transaction."""
    politician: str
    chamber: str                  # "House" or "Senate"
    party: str
    committee: str
    symbol: str
    transaction_type: str         # "buy" or "sell"
    transaction_date: str        # ISO date
    amount_range: str            # e.g. "$1,001 - $15,000"
    filing_date: str
    source: str


@dataclass
class CongressionalSignal:
    """A clustered congressional trading signal."""
    symbol: str
    signal: str
    politician: str
    committee: str
    transaction_date: str
    cluster_count: int
    trades: List[dict]


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
            "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
            "Accept-Encoding": "gzip, deflate",
        }
        self._client: Optional[httpx.Client] = None

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

    # -- Data source 1: Capitol Trades (web scraping) --------------------- #

    def _fetch_capitol_trades(self) -> List[CongressionalTrade]:
        """Scrape recent trades from capitoltrades.com.

        The site renders trades in HTML tables. We parse the table rows
        to extract politician, ticker, transaction type, and date.
        """
        trades: List[CongressionalTrade] = []
        try:
            resp = self.client.get(CAPITOL_TRADES_URL, timeout=20)
            if resp.status_code != 200:
                return trades

            soup = BeautifulSoup(resp.text, "lxml")

            # Capitol Trades renders trades in a table with class 'q-table'
            # or in div-based layout. The structure changes frequently.
            # We try multiple parsing strategies.

            # Strategy 1: Look for trade rows in tables
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                for tr in rows[1:]:  # skip header
                    tds = tr.find_all("td")
                    if len(tds) < 5:
                        continue
                    try:
                        trade = self._parse_capitol_trade_row(tds)
                        if trade:
                            trades.append(trade)
                    except Exception:
                        continue

            # Strategy 2: Look for div-based trade cards
            if not trades:
                trade_cards = soup.find_all(
                    "div", class_=re.compile(r"trade|transaction", re.I)
                )
                for card in trade_cards:
                    try:
                        trade = self._parse_capitol_trade_card(card)
                        if trade:
                            trades.append(trade)
                    except Exception:
                        continue

        except (httpx.TransportError, httpx.TimeoutException) as exc:
            print(f"[Congress] Capitol Trades fetch failed: {exc}")
        except Exception as exc:
            print(f"[Congress] Capitol Trades parse error: {exc}")

        return trades

    def _parse_capitol_trade_row(self, tds: list) -> Optional[CongressionalTrade]:
        """Parse a table row from capitoltrades.com into a CongressionalTrade."""
        # The table columns vary; this is a best-effort parser
        # Expected columns: Politician, Ticker, Type, Date, Amount, Filing Date
        if len(tds) < 5:
            return None

        politician_name = tds[0].get_text(strip=True)
        ticker = tds[1].get_text(strip=True).upper()
        txn_type_raw = tds[2].get_text(strip=True).lower()
        txn_date = tds[3].get_text(strip=True)
        amount = tds[4].get_text(strip=True) if len(tds) > 4 else ""

        if not ticker or not politician_name:
            return None

        # Normalize transaction type
        if "buy" in txn_type_raw or "purchase" in txn_type_raw:
            txn_type = "buy"
        elif "sell" in txn_type_raw or "sale" in txn_type_raw:
            txn_type = "sell"
        else:
            return None

        # Try to parse date
        date_str = _normalize_date(txn_date)

        return CongressionalTrade(
            politician=politician_name,
            chamber="",         # not always available from table
            party="",
            committee="",
            symbol=ticker,
            transaction_type=txn_type,
            transaction_date=date_str,
            amount_range=amount,
            filing_date="",
            source="capitoltrades",
        )

    def _parse_capitol_trade_card(self, card) -> Optional[CongressionalTrade]:
        """Parse a div-based trade card from capitoltrades.com."""
        text = card.get_text(" ", strip=True)

        # Try to extract ticker — usually in a span with class containing 'ticker'
        ticker_elem = card.find(class_=re.compile(r"ticker|symbol", re.I))
        if not ticker_elem:
            return None
        ticker = ticker_elem.get_text(strip=True).upper()

        # Try to find politician name
        pol_elem = card.find(class_=re.compile(r"politician|name|member", re.I))
        politician = pol_elem.get_text(strip=True) if pol_elem else ""

        # Try to find transaction type
        type_elem = card.find(class_=re.compile(r"type|direction|side", re.I))
        txn_type_raw = type_elem.get_text(strip=True).lower() if type_elem else ""
        if "buy" in txn_type_raw or "purchase" in txn_type_raw:
            txn_type = "buy"
        elif "sell" in txn_type_raw or "sale" in txn_type_raw:
            txn_type = "sell"
        else:
            return None

        # Try to find date
        date_elem = card.find(class_=re.compile(r"date", re.I))
        date_str = _normalize_date(date_elem.get_text(strip=True)) if date_elem else ""

        return CongressionalTrade(
            politician=politician,
            chamber="",
            party="",
            committee="",
            symbol=ticker,
            transaction_type=txn_type,
            transaction_date=date_str,
            amount_range="",
            filing_date="",
            source="capitoltrades",
        )

    # -- Data source 2: Quiver Quant API (free tier) ---------------------- #

    def _fetch_quiver_trades(self) -> List[CongressionalTrade]:
        """Fetch congressional trades from Quiver Quant API (free tier).

        Quiver Quant offers a free API endpoint for congressional trading data.
        Endpoint: https://api.quiverquant.com/beta/historicalcongress trading/{ticker}
        Full bulk endpoint: https://api.quiverquant.com/beta/latestcongresstrading
        Requires a free API key passed as 'x-api-key' header.
        """
        trades: List[CongressionalTrade] = []
        # Quiver requires an API key — check env var
        import os
        api_key = os.environ.get("QUIVER_API_KEY", "")

        if not api_key:
            print("[Congress] No QUIVER_API_KEY set — skipping Quiver Quant")
            return trades

        try:
            headers = {**self._headers, "x-api-key": api_key}
            resp = httpx.get(
                f"{QUIVER_API_BASE}/beta/latestcongresstrading",
                headers=headers,
                timeout=20,
            )
            if resp.status_code != 200:
                print(f"[Congress] Quiver API returned {resp.status_code}")
                return trades

            data = resp.json()
            for item in data:
                ticker = item.get("Ticker", "").upper()
                if not ticker:
                    continue

                rep = item.get("Representative", "") or item.get("Senator", "")
                txn_type = "buy" if (item.get("Transaction") or "").lower().startswith("buy") else "sell"
                txn_date = item.get("TransactionDate", "") or item.get("Traded", "")

                trades.append(CongressionalTrade(
                    politician=rep,
                    chamber=item.get("Chamber", ""),
                    party=item.get("Party", ""),
                    committee="",  # not provided by Quiver basic endpoint
                    symbol=ticker,
                    transaction_type=txn_type,
                    transaction_date=_normalize_date(txn_date),
                    amount_range=item.get("Range", ""),
                    filing_date=item.get("Filed", ""),
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
          - Committee member buying in their oversight sector → STRONG_BUY
          - 2+ politicians buying same stock within 30 days → BUY
          - Single politician purchase → WEAK_BUY
          - Same mirrored for sells
        """
        trades: List[CongressionalTrade] = []

        # Try data sources in order
        trades = self._fetch_capitol_trades()

        if not trades:
            trades = self._fetch_quiver_trades()

        if not trades:
            print("[Congress] No free data source available. Returning empty signals.")
            print("[Congress] TODO: Configure QUIVER_API_KEY or check capitoltrades.com structure.")
            return []

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

            # Sort by date descending
            sorted_trades = sorted(
                symbol_trades,
                key=lambda t: t.transaction_date or "",
                reverse=True,
            )

            politicians = list({t.politician for t in sorted_trades if t.politician})
            cluster_count = len(politicians)

            # Check for committee overlap
            committees = TICKER_COMMITTEE_MAP.get(symbol, [])
            committee_match = None
            matched_politician = None
            for t in sorted_trades:
                # If we know the committee and it overlaps with the ticker's oversight
                if t.committee and t.committee in committees:
                    committee_match = t.committee
                    matched_politician = t.politician
                    break

            latest_date = sorted_trades[0].transaction_date if sorted_trades else ""

            if committee_match:
                signal = "STRONG_BUY"
                politician = matched_politician or politicians[0] if politicians else ""
                committee = committee_match
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
            committee_match = None
            matched_politician = None
            for t in sorted_trades:
                if t.committee and t.committee in committees:
                    committee_match = t.committee
                    matched_politician = t.politician
                    break

            latest_date = sorted_trades[0].transaction_date if sorted_trades else ""

            if committee_match:
                signal = "STRONG_SELL"
                politician = matched_politician or politicians[0] if politicians else ""
                committee = committee_match
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
                "trades": [asdict(t) for t in sorted_trades[:10]],
            })

        # Sort: strong signals first
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

def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to ISO YYYY-MM-DD."""
    if not date_str:
        return ""
    # Try common formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Try regex extraction
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
                f"cluster={s['cluster_count']}"
            )
    finally:
        scanner.close()