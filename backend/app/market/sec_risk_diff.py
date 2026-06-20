#!/usr/bin/env python3
"""SEC Risk Factor Diff Signal Generator

Tracks year-over-year changes in 10-K risk factor disclosures. When companies
add new risk language (especially around AI, cybersecurity, supply chain), it's
a forward-looking negative signal.

Data source: RiskDiff.com (free) or SEC EDGAR full-text search.
"""

from __future__ import annotations

import httpx
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class RiskFactorChange:
    """A single risk factor change for a company."""
    symbol: str
    company_name: str
    risk_category: str  # e.g., "AI", "Cybersecurity", "Supply Chain", "Regulatory"
    change_type: str  # "added", "modified", "removed"
    description: str
    filing_date: str
    severity: str  # "high", "medium", "low"
    reasoning: str


# Categories of risk factor changes that matter for trading
RISK_CATEGORIES = {
    "AI": {
        "keywords": ["artificial intelligence", "machine learning", "generative ai", "large language model", "automated", "algorithmic"],
        "severity": "high",
        "impact": "New AI risk language suggests competitive disruption or regulatory concern",
    },
    "Cybersecurity": {
        "keywords": ["cybersecurity", "data breach", "ransomware", "security incident", "information security"],
        "severity": "high",
        "impact": "New cybersecurity risk = potential vulnerability or recent incident",
    },
    "Supply Chain": {
        "keywords": ["supply chain", "supplier", "procurement", "raw material", "logistics"],
        "severity": "medium",
        "impact": "Supply chain risk addition = potential disruption ahead",
    },
    "Regulatory": {
        "keywords": ["regulation", "regulatory", "compliance", "legislation", "antitrust", "sanction"],
        "severity": "medium",
        "impact": "New regulatory risk = policy headwind",
    },
    "Geopolitical": {
        "keywords": ["geopolitical", "trade war", "tariff", "sanction", "conflict", "export control"],
        "severity": "medium",
        "impact": "Geopolitical risk = international exposure concern",
    },
    "Climate": {
        "keywords": ["climate", "carbon", "emission", "environmental", "sustainability", "ESG"],
        "severity": "low",
        "impact": "Climate risk = long-term regulatory exposure",
    },
}


class SECRiskDiffScanner:
    """Scan SEC 10-K filings for risk factor changes."""

    def __init__(self):
        self.base_url = "https://data.sec.gov/submissions"

    def _get_cik_map(self) -> Dict[str, str]:
        """Get symbol → CIK mapping from SEC."""
        # Use a simplified mapping for top S&P 500 companies
        # In production, fetch from SEC tickers file
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            r = httpx.get(url, timeout=30, headers={"User-Agent": "LeadSignal/1.0 contact@dmeomaha.com"})
            if r.status_code == 200:
                data = r.json()
                # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
                cik_map = {}
                for v in data.values():
                    ticker = v.get("ticker", "")
                    cik = str(v.get("cik_str", "")).zfill(10)
                    if ticker:
                        cik_map[ticker] = cik
                return cik_map
        except Exception as e:
            print(f"WARN cik_map: {e}")
        return {}

    def fetch_recent_filings(self, symbol: str, filing_type: str = "10-K") -> List[dict]:
        """Fetch recent SEC filings for a symbol."""
        cik_map = getattr(self, '_cik_map', None)
        if not cik_map:
            self._cik_map = self._get_cik_map()
            cik_map = self._cik_map

        cik = cik_map.get(symbol)
        if not cik:
            return []

        try:
            url = f"{self.base_url}/CIK{cik}.json"
            r = httpx.get(url, timeout=30, headers={"User-Agent": "LeadSignal/1.0 contact@dmeomaha.com"})
            if r.status_code != 200:
                return []

            data = r.json()
            filings = data.get("filings", {}).get("recent", {})

            # Filter for 10-K filings
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])

            results = []
            for i, form in enumerate(forms):
                if form == filing_type and i < len(dates):
                    results.append({
                        "form": form,
                        "date": dates[i],
                        "accession": accessions[i].replace("-", ""),
                        "cik": cik,
                    })
            return results
        except Exception as e:
            print(f"WARN fetch_filings {symbol}: {e}")
            return []

    def fetch_risk_factors(self, symbol: str, accession: str, cik: str) -> Optional[str]:
        """Fetch risk factor section from a 10-K filing."""
        # SEC EDGAR full-text search or direct filing access
        # This is simplified — in production, parse the actual 10-K document
        try:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=10"
            r = httpx.get(url, timeout=30, headers={"User-Agent": "LeadSignal/1.0 contact@dmeomaha.com"})
            # Note: Full 10-K parsing requires downloading the document and extracting Item 1A
            # For now, return None — the RiskDiff.com integration below is the primary path
            return None
        except Exception:
            return None

    def get_risk_signals(self, symbols: List[str]) -> List[RiskFactorChange]:
        """Get risk factor change signals for a list of symbols.

        Primary approach: Use RiskDiff.com API (if available)
        Fallback: Use SEC EDGAR to detect new filings and flag for review
        """
        signals = []

        # Try RiskDiff.com (free, tracks 431 S&P 500 companies)
        try:
            # RiskDiff doesn't have a documented public API, but we can try
            r = httpx.get("https://riskdiff.com/api/changes", timeout=15,
                         headers={"User-Agent": "LeadSignal/1.0"})
            if r.status_code == 200:
                data = r.json()
                for item in data.get("changes", []):
                    symbol = item.get("ticker", "")
                    if symbol in symbols:
                        category = item.get("category", "Unknown")
                        cat_info = RISK_CATEGORIES.get(category, {})
                        signals.append(RiskFactorChange(
                            symbol=symbol,
                            company_name=item.get("company", ""),
                            risk_category=category,
                            change_type=item.get("change_type", "added"),
                            description=item.get("description", ""),
                            filing_date=item.get("filing_date", ""),
                            severity=cat_info.get("severity", "medium"),
                            reasoning=cat_info.get("impact", "Risk factor change detected"),
                        ))
        except Exception as e:
            print(f"WARN riskdiff API: {e}")

        # Fallback: check for recent 10-K filings via SEC EDGAR
        if not signals:
            print("[RISK DIFF] RiskDiff API unavailable, checking SEC EDGAR for recent 10-K filings...")
            for symbol in symbols[:50]:  # Limit to top 50 for rate limiting
                filings = self.fetch_recent_filings(symbol, "10-K")
                if filings:
                    latest = filings[0]
                    # Flag any 10-K filed in last 90 days as "review needed"
                    filing_date = latest.get("date", "")
                    if filing_date:
                        try:
                            fd = datetime.strptime(filing_date, "%Y-%m-%d")
                            days_ago = (datetime.now() - fd).days
                            if days_ago < 90:
                                signals.append(RiskFactorChange(
                                    symbol=symbol,
                                    company_name="",
                                    risk_category="Filing",
                                    change_type="new_filing",
                                    description=f"New 10-K filed {filing_date}",
                                    filing_date=filing_date,
                                    severity="low",
                                    reasoning=f"Recent 10-K filing — risk factors may have changed",
                                ))
                        except Exception:
                            pass

        return signals

    def get_signals_for_scan(self, symbols: List[str]) -> List[dict]:
        """Get signals formatted for the daily scan integration."""
        risk_signals = self.get_risk_signals(symbols)
        return [asdict(s) for s in risk_signals]


def get_risk_diff_signals(symbols: List[str]) -> List[dict]:
    """Quick entry point for the daily scan."""
    scanner = SECRiskDiffScanner()
    return scanner.get_signals_for_scan(symbols)


if __name__ == "__main__":
    scanner = SECRiskDiffScanner()
    symbols = ["AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOGL", "NFLX", "TSLA", "JPM", "V"]
    signals = scanner.get_signals_for_scan(symbols)
    print(f"Found {len(signals)} risk factor change signals")
    for s in signals:
        print(f"  {s['symbol']}: {s['risk_category']} ({s['change_type']}) — {s['description'][:80]}")