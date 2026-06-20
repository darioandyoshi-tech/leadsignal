#!/usr/bin/env python3
"""SEC Form 4 insider trading scanner.

Fetches recent Form 4 filings from SEC EDGAR, parses transaction codes
(P = purchase, S = sale, A = award/acquisition), and detects clusters
of insider buying at the same company within a 30-day window.

Rate limiting: SEC requires a descriptive User-Agent header and allows
a maximum of 10 requests per second. We use a conservative delay.

References:
  - https://www.sec.gov/cgi-bin/browse-edgar (latest filings listing)
  - https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/ownership.xml
  - Form 4 transaction codes: 17 CFR 240.16b-3 / SEC EDGAR docs
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from lxml import etree

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SEC_USER_AGENT = "LeadSignal/1.0 contact@dmeomaha.com"
SEC_BASE = "https://www.sec.gov"
BROWSE_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=4&company=&dateb=&owner=only"
    "&count={count}&search_text=&action=getcurrent"
)

# Transaction codes (from SEC Form 4 instructions)
# P  – Open market or private purchase
# S  – Open market or private sale
# A  – Award, grant, allocation, or other acquisition (e.g. RSU)
# D  – Disposition in good faith to a tax-advantaged plan
# F  – Payment of exercise price or tax obligation using securities
# G  – Gift
# I  – Disposition of shares to issuer
# M  – Exercise or conversion of derivative security exempt rule 16b-3
# X  – Exercise or conversion of derivative security exempt rule 16b-6(d)
# C  – Conversion of derivative security (non-exempt)
# W  – Acquisition or disposition by will or estate
# J  – Other acquisition or disposition
# H  – Expiration (or cancellation) of short position
# L  – Acquisition or disposition by loan
# O  – Exercise of derivative security resulting from a post-transaction
# U  – Disposition in good faith to tax-advantaged plan
PURCHASE_CODES = {"P"}          # strong buy signal
SALE_CODES = {"S"}              # sell signal
ACQUISITION_CODES = {"P", "A", "M", "C"}  # any acquisition (weaker buy)
DISPOSITION_CODES = {"S", "D", "F", "G", "I"}  # any disposition

CLUSTER_THRESHOLD = 3      # 3+ insiders buying same stock in 30 days
CLUSTER_WINDOW_DAYS = 30
DEFAULT_FETCH_COUNT = 100    # filings per page
MAX_PAGES = 5               # max pages to paginate (500 filings)
REQUEST_DELAY_SEC = 0.15    # ~6.5 req/sec — well under 10/sec limit


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class Form4Transaction:
    """A single transaction parsed from a Form 4 filing."""
    symbol: str
    reporting_owner: str
    owner_cik: str
    issuer_name: str
    issuer_cik: str
    transaction_code: str
    transaction_date: str          # ISO date
    shares: Optional[float]
    price_per_share: Optional[float]
    acquired_disposed: str         # "A" or "D"
    filing_date: str
    accession_number: str
    form_url: str


@dataclass
class InsiderSignal:
    """A clustered insider trading signal."""
    symbol: str
    signal: str                     # "STRONG_BUY" / "BUY" / "SELL"
    cluster_count: int
    last_transaction_date: str
    insiders: List[str]
    transactions: List[dict]


# --------------------------------------------------------------------------- #
# SEC Form 4 Scanner
# --------------------------------------------------------------------------- #

class InsiderTradeScanner:
    """Scan SEC EDGAR for recent Form 4 insider transactions.

    Usage:
        scanner = InsiderTradeScanner()
        transactions = scanner.fetch_recent_form4_filings()
        signals = scanner.get_insider_signals()
    """

    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        fetch_count: int = DEFAULT_FETCH_COUNT,
        max_pages: int = MAX_PAGES,
        request_delay: float = REQUEST_DELAY_SEC,
    ) -> None:
        self.user_agent = user_agent
        self.fetch_count = fetch_count
        self.max_pages = max_pages
        self.request_delay = request_delay
        self._headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,*/*",
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
        self._client: Optional[httpx.Client] = None

    # -- HTTP helper ------------------------------------------------------ #

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self._headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    def _get(self, url: str) -> Optional[httpx.Response]:
        """Rate-limited GET with retry."""
        for attempt in range(3):
            try:
                time.sleep(self.request_delay)
                resp = self.client.get(url)
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 429:
                    # Rate limited — back off
                    time.sleep(2.0 * (attempt + 1))
                    continue
                # Non-retryable
                return resp
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
        return None

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    # -- Step 1: List recent Form 4 filings ------------------------------- #

    def _parse_filing_list(self, html: str) -> List[dict]:
        """Parse the browse-edgar HTML page and extract filing metadata.

        Returns list of dicts with keys:
            company, cik, role, form_type, html_url, text_url,
            accession_number, accepted, filing_date
        """
        soup = BeautifulSoup(html, "lxml")

        # Find the filings table (has th with 'Form')
        filing_table = None
        for table in soup.find_all("table"):
            ths = table.find_all("th")
            if ths and any("Form" in th.get_text(strip=True) for th in ths):
                filing_table = table
                break

        if not filing_table:
            return []

        filings: List[dict] = []
        rows = filing_table.find_all("tr")

        # The table alternates: company row, then filing data row(s)
        current_company = None
        current_cik = None
        current_role = None

        for tr in rows:
            tds = tr.find_all("td")
            if not tds:
                continue

            # Company rows have a single td with a link to getcompany
            company_link = tr.find("a", href=re.compile(r"getcompany.*CIK="))
            if company_link and len(tds) <= 3:
                text = company_link.get_text(strip=True)
                # Pattern: "Company Name (CIK) (Role)"
                m = re.match(
                    r"(.+?)\s*\((\d+)\)\s*\((Reporting|Issuer|Filer|Subject|Filed by)\)",
                    text,
                )
                if m:
                    current_company = m.group(1).strip()
                    current_cik = m.group(2).strip()
                    current_role = m.group(3).strip()
                continue

            # Filing data rows have Form type, format links, description, dates
            form_type = tds[0].get_text(strip=True) if tds else ""
            if form_type != "4":
                continue

            # Find html/text links
            html_link = None
            text_link = None
            for a in tr.find_all("a", href=True):
                href = a["href"]
                if href.endswith("-index.htm"):
                    html_link = href
                elif href.endswith(".txt"):
                    text_link = href

            if not html_link:
                continue

            # Parse description for accession number
            desc_text = ""
            if len(tds) > 2:
                desc_text = tds[2].get_text(strip=True)
            accession_match = re.search(r"Accession Number:\s*([\w\-]+)", desc_text)

            # Parse dates
            accepted = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            filing_date = tds[4].get_text(strip=True) if len(tds) > 4 else ""

            filing = {
                "company": current_company or "",
                "cik": current_cik or "",
                "role": current_role or "",
                "form_type": "4",
                "html_url": html_link,
                "text_url": text_link or "",
                "accession_number": accession_match.group(1) if accession_match else "",
                "accepted": accepted,
                "filing_date": filing_date,
            }
            filings.append(filing)

        return filings

    def fetch_recent_filings_list(self) -> List[dict]:
        """Fetch the list of recent Form 4 filings from SEC EDGAR.

        Paginates through up to ``max_pages`` pages of ``fetch_count`` filings
        each. Returns a de-duplicated list of filing metadata dicts.
        """
        all_filings: List[dict] = []
        seen_accessions: Set[str] = set()

        for page in range(self.max_pages):
            start = page * self.fetch_count
            url = BROWSE_URL.format(count=self.fetch_count)
            if start > 0:
                url += f"&start={start}"

            resp = self._get(url)
            if not resp or resp.status_code != 200:
                break

            filings = self._parse_filing_list(resp.text)
            if not filings:
                break

            new_count = 0
            for f in filings:
                acc = f.get("accession_number", "")
                if acc and acc not in seen_accessions:
                    seen_accessions.add(acc)
                    all_filings.append(f)
                    new_count += 1

            if new_count == 0:
                break

        return all_filings

    # -- Step 2: Fetch and parse Form 4 XML -------------------------------- #

    def _fetch_form4_xml(self, html_index_url: str) -> Optional[str]:
        """Fetch the ownership.xml from a filing's index page.

        The html_index_url is like:
            /Archives/edgar/data/{cik}/{accession_dir}/{accession}-index.htm
        We parse the index page to find the ownership.xml link, then fetch it.
        """
        full_url = urljoin(SEC_BASE, html_index_url)
        resp = self._get(full_url)
        if not resp or resp.status_code != 200:
            return None

        # Parse index page to find the Form 4 XML link
        # The XML file may be named ownership.xml, form4.xml, or similar
        # IMPORTANT: Skip xslF345X06/*.xml links — those are HTML-rendered versions
        soup = BeautifulSoup(resp.text, "lxml")
        xml_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Skip XSL-rendered versions (they return HTML, not XML)
            if "/xslF345X" in href:
                continue
            if href.endswith("ownership.xml") or href.endswith("form4.xml"):
                xml_url = href
                break

        if not xml_url:
            return None

        # Fetch the XML
        full_xml_url = urljoin(SEC_BASE, xml_url)
        resp2 = self._get(full_xml_url)
        if not resp2 or resp2.status_code != 200:
            return None

        return resp2.text

    def _parse_form4_xml(self, xml_text: str, filing_meta: dict) -> List[Form4Transaction]:
        """Parse a Form 4 XML document into transaction objects."""
        transactions: List[Form4Transaction] = []
        try:
            root = etree.fromstring(xml_text.encode("utf-8"), parser=etree.XMLParser(recover=True))
        except etree.XMLSyntaxError:
            return transactions

        # Extract issuer info
        issuer = root.find(".//issuer")
        if issuer is None:
            return transactions

        symbol = _xml_text(issuer, "issuerTradingSymbol")
        issuer_name = _xml_text(issuer, "issuerName")
        issuer_cik = _xml_text(issuer, "issuerCik")

        # Extract reporting owner
        owner = root.find(".//reportingOwner")
        owner_name = ""
        owner_cik = ""
        if owner is not None:
            owner_name = (owner.findtext(".//rptOwnerName") or "").strip()
            owner_cik = (owner.findtext(".//rptOwnerCik") or "").strip()

        # Parse non-derivative transactions
        for txn in root.findall(".//nonDerivativeTransaction"):
            t = self._parse_transaction_element(
                txn, symbol, issuer_name, issuer_cik, owner_name, owner_cik, filing_meta
            )
            if t:
                transactions.append(t)

        # Parse derivative transactions too (exercises, conversions)
        for txn in root.findall(".//derivativeTransaction"):
            t = self._parse_transaction_element(
                txn, symbol, issuer_name, issuer_cik, owner_name, owner_cik, filing_meta
            )
            if t:
                transactions.append(t)

        return transactions

    def _parse_transaction_element(
        self,
        txn_element,
        symbol: str,
        issuer_name: str,
        issuer_cik: str,
        owner_name: str,
        owner_cik: str,
        filing_meta: dict,
    ) -> Optional[Form4Transaction]:
        """Parse a single <nonDerivativeTransaction> or <derivativeTransaction> element."""
        # Transaction date
        txn_date = _xml_text(txn_element, ".//transactionDate/value")

        # Transaction coding
        txn_coding = txn_element.find(".//transactionCoding")
        txn_code = txn_coding.findtext("transactionCode") if txn_coding is not None else ""

        # Transaction amounts
        shares_val = _xml_text(txn_element, ".//transactionShares/value")
        price_val = _xml_text(txn_element, ".//transactionPricePerShare/value")
        ad_code = _xml_text(txn_element, ".//transactionAcquiredDisposedCode/value")

        shares = _to_float(shares_val)
        price = _to_float(price_val)

        return Form4Transaction(
            symbol=symbol or "",
            reporting_owner=owner_name,
            owner_cik=owner_cik,
            issuer_name=issuer_name,
            issuer_cik=issuer_cik,
            transaction_code=txn_code or "",
            transaction_date=txn_date or "",
            shares=shares,
            price_per_share=price,
            acquired_disposed=ad_code or "",
            filing_date=filing_meta.get("filing_date", "").split("\n")[0],
            accession_number=filing_meta.get("accession_number", ""),
            form_url=filing_meta.get("html_url", ""),
        )

    # -- Step 3: Fetch all transactions ----------------------------------- #

    def fetch_recent_transactions(self) -> List[Form4Transaction]:
        """Fetch and parse all recent Form 4 transactions.

        This is the heavy-lifting method: lists filings, then fetches each
        Form 4 XML and parses transactions.
        """
        filings = self.fetch_recent_filings_list()
        all_transactions: List[Form4Transaction] = []

        for filing in filings:
            xml_text = self._fetch_form4_xml(filing.get("html_url", ""))
            if not xml_text:
                continue
            txns = self._parse_form4_xml(xml_text, filing)
            all_transactions.extend(txns)

        return all_transactions

    # -- Step 4: Cluster detection & signals ------------------------------ #

    def get_insider_signals(self) -> List[dict]:
        """Main entry point: detect insider trading clusters and return signals.

        Returns a list of dicts with keys:
            symbol, signal, cluster_count, last_transaction_date,
            insiders, transactions

        Signal logic:
          - 3+ insiders purchasing (code P) same stock within 30 days → STRONG_BUY
          - 1-2 insiders purchasing (code P) → BUY
          - 3+ insiders selling (code S) same stock within 30 days → STRONG_SELL
          - 1-2 insiders selling (code S) → SELL
          - Single large purchase (>100k shares) → BUY
        """
        transactions = self.fetch_recent_transactions()
        if not transactions:
            return []

        # Group purchase and sale transactions by symbol
        purchases: Dict[str, List[Form4Transaction]] = defaultdict(list)
        sales: Dict[str, List[Form4Transaction]] = defaultdict(list)

        for txn in transactions:
            if not txn.symbol:
                continue
            if txn.transaction_code in PURCHASE_CODES:
                purchases[txn.symbol].append(txn)
            elif txn.transaction_code in SALE_CODES:
                sales[txn.symbol].append(txn)

        signals: List[dict] = []

        # Detect purchase clusters
        for symbol, txns in purchases.items():
            # Sort by date descending
            txns_sorted = sorted(txns, key=lambda t: t.transaction_date or "", reverse=True)
            if not txns_sorted:
                continue

            # Find unique insiders
            insiders = list({t.reporting_owner for t in txns_sorted if t.reporting_owner})
            cluster_count = len(insiders)

            # Check if transactions are within the cluster window
            latest_date_str = txns_sorted[0].transaction_date
            if latest_date_str:
                try:
                    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
                    window_start = latest_date - timedelta(days=CLUSTER_WINDOW_DAYS)
                    in_window = [
                        t for t in txns_sorted
                        if t.transaction_date
                        and _parse_date(t.transaction_date) >= window_start
                    ]
                    window_insiders = list({t.reporting_owner for t in in_window if t.reporting_owner})
                    cluster_count = len(window_insiders)
                except (ValueError, TypeError):
                    pass

            if cluster_count >= CLUSTER_THRESHOLD:
                signal = "STRONG_BUY"
            elif cluster_count >= 2:
                signal = "BUY"
            elif len(txns_sorted) == 1:
                # Single large purchase
                t = txns_sorted[0]
                if t.shares and t.shares >= 100_000:
                    signal = "BUY"
                else:
                    continue  # skip single small purchases
            else:
                signal = "BUY"

            signals.append({
                "symbol": symbol,
                "signal": signal,
                "cluster_count": cluster_count,
                "last_transaction_date": latest_date_str or "",
                "insiders": insiders,
                "transactions": [asdict(t) for t in txns_sorted[:10]],
            })

        # Detect sale clusters
        for symbol, txns in sales.items():
            txns_sorted = sorted(txns, key=lambda t: t.transaction_date or "", reverse=True)
            if not txns_sorted:
                continue

            insiders = list({t.reporting_owner for t in txns_sorted if t.reporting_owner})
            cluster_count = len(insiders)

            latest_date_str = txns_sorted[0].transaction_date
            if latest_date_str:
                try:
                    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
                    window_start = latest_date - timedelta(days=CLUSTER_WINDOW_DAYS)
                    in_window = [
                        t for t in txns_sorted
                        if t.transaction_date
                        and _parse_date(t.transaction_date) >= window_start
                    ]
                    window_insiders = list({t.reporting_owner for t in in_window if t.reporting_owner})
                    cluster_count = len(window_insiders)
                except (ValueError, TypeError):
                    pass

            if cluster_count >= CLUSTER_THRESHOLD:
                signal = "STRONG_SELL"
            elif cluster_count >= 2:
                signal = "SELL"
            else:
                continue

            signals.append({
                "symbol": symbol,
                "signal": signal,
                "cluster_count": cluster_count,
                "last_transaction_date": latest_date_str or "",
                "insiders": insiders,
                "transactions": [asdict(t) for t in txns_sorted[:10]],
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

def _xml_text(element, path: str) -> str:
    """Safely extract text from an XML element at the given xpath."""
    if element is None:
        return ""
    found = element.find(path) if isinstance(path, str) else None
    if found is not None:
        return (found.text or "").strip()
    return ""


def _to_float(val: str) -> Optional[float]:
    """Convert a string to float, returning None on failure."""
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_date(date_str: str) -> datetime:
    """Parse an ISO date string, returning a minimal datetime on failure."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.min


# --------------------------------------------------------------------------- #
# Module entry point for manual testing
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    scanner = InsiderTradeScanner(fetch_count=100, max_pages=2)
    try:
        print("Fetching recent Form 4 filings from SEC EDGAR...")
        signals = scanner.get_insider_signals()
        print(f"\nFound {len(signals)} insider signals:\n")
        for s in signals:
            print(
                f"  {s['symbol']:6s}  {s['signal']:12s}  "
                f"cluster={s['cluster_count']}  "
                f"date={s['last_transaction_date']}  "
                f"insiders={s['insiders']}"
            )
    finally:
        scanner.close()