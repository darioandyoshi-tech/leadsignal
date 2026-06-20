"""Earnings Call NLP & Post-Earnings Announcement Drift (PEAD) Signal.

After earnings, stocks with positive EPS surprise + positive Q&A sentiment
tend to drift upward for 5-20 days.  Negative surprise + negative Q&A →
downward drift.  The Q&A section of earnings calls is especially predictive
because it is less scripted than prepared remarks.

This module:
1. Fetches recent earnings dates and results via yfinance.
2. For stocks that reported in the last 1–5 days, optionally fetches the
   earnings call transcript Q&A section from Motley Fool.
3. Runs FinBERT sentiment analysis on the Q&A text.
4. Generates a PEAD signal: positive surprise + positive Q&A = BUY,
   negative + negative = AVOID.

Usage::

    from app.market.earnings_nlp import EarningsNLPScanner

    scanner = EarningsNLPScanner()
    signals = scanner.get_earnings_signals(["AAPL", "MSFT", "NVDA"])
    upcoming = scanner.get_upcoming_earnings(days_ahead=7)
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Dict, List, Optional, Tuple

import httpx
import yfinance as yf

from app.market.sentiment import FinbertSentimentAnalyzer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Top 100 S&P 500 stocks (approximate, by market cap) — used for upcoming
# earnings scans.  Keeping this list focused avoids excessive API calls.
SP500_TOP_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK.B",
    "LLY", "AVGO", "TSLA", "JPM", "V", "XOM", "UNH", "MA", "PG", "JNJ",
    "HD", "COST", "ABBV", "BAC", "MRK", "CVX", "KO", "PEP", "ORCL",
    "WMT", "CRM", "ADBE", "AMD", "NFLX", "CSCO", "TMO", "ACN", "ABT",
    "LIN", "DHR", "TXN", "INTC", "NEE", "PM", "CMG", "IBM", "QCOM",
    "LOW", "UPS", "SPGI", "INTU", "AMGN", "ISRG", "CAT", "GS", "MS",
    "BLK", "GE", "BA", "DE", "RTX", "HON", "LMT", "SBUX", "MDT",
    "SYK", "BMY", "GILD", "AMT", "PLD", "COP", "SLB", "EOG", "OXY",
    "FCX", "NEM", "WMB", "ETN", "ITW", "PH", "ROK", "DOV", "PNC",
    "USB", "TFC", "COF", "SCHW", "AXP", "BK", "STT", "T", "VZ", "TMUS",
    "DIS", "CMCSA", "FOX", "WBA", "MDLZ", "CL", "KMB", "MO", "TGT",
]

# Motley Fool transcript base URL
FOOL_TRANSCRIPTS_URL = "https://www.fool.com/earnings-call-transcripts/"

# Rate limiting for web requests
_MIN_REQUEST_INTERVAL = 1.0  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rate_limit(source: str, last_times: Dict[str, float]) -> None:
    """Simple per-source rate limiter."""
    now = time.monotonic()
    last = last_times.get(source, 0.0)
    elapsed = now - last
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    last_times[source] = time.monotonic()


def _strip_html(html: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_qa(transcript_text: str) -> Tuple[str, str]:
    """Split a full transcript into (prepared_remarks, qa_section).

    The Q&A section usually starts after a phrase like "we will now take
    your questions" or "Q&A".  If we can't find the boundary we return
    (full_text, "").
    """
    lower = transcript_text.lower()

    # Common Q&A boundary markers
    markers = [
        "we will now take your questions",
        "we'll now take your questions",
        "operator, we are ready for questions",
        "operator, we're ready for questions",
        "i will now turn the call over to the operator",
        "question-and-answer session",
        "questions and answers",
        "qa session",
        "operator:  we will now",
    ]

    qa_start = -1
    for marker in markers:
        idx = lower.find(marker)
        if idx >= 0:
            qa_start = idx
            break

    if qa_start < 0:
        # Fallback: look for the first "Operator:" after the prepared remarks
        # This is usually the Q&A start
        operator_indices = [m.start() for m in re.finditer(r"Operator:", transcript_text, re.I)]
        if len(operator_indices) >= 2:
            qa_start = operator_indices[0]
        elif operator_indices:
            qa_start = operator_indices[0]

    if qa_start < 0:
        return transcript_text, ""

    prepared = transcript_text[:qa_start].strip()
    qa = transcript_text[qa_start:].strip()
    return prepared, qa


def _chunk_text(text: str, max_words: int = 200) -> List[str]:
    """Split long text into chunks that FinBERT can process efficiently.

    FinBERT has a 512-token limit.  We use 200-word chunks which is safely
    within limits while providing enough context for sentiment.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks: List[str] = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words])
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class EarningsNLPScanner:
    """Earnings NLP scanner with PEAD signal generation.

    Parameters
    ----------
    fetch_transcripts : bool
        Whether to attempt fetching earnings call transcripts from Motley
        Fool.  If False, PEAD signals are based solely on EPS surprise.
    max_transcript_words : int
        Maximum number of words to analyse from the Q&A section.  Long
        transcripts are chunked and the first *max_transcript_words* are
        used to keep inference time reasonable.
    """

    def __init__(
        self,
        fetch_transcripts: bool = True,
        max_transcript_words: int = 4000,
    ):
        self.fetch_transcripts = fetch_transcripts
        self.max_transcript_words = max_transcript_words
        self._sentiment: Optional[FinbertSentimentAnalyzer] = None
        self._last_request: Dict[str, float] = {}
        self._transcript_cache: Dict[str, Tuple[str, datetime]] = {}

    # ------------------------------------------------------------------
    # Lazy-loaded FinBERT
    # ------------------------------------------------------------------
    @property
    def sentiment_analyzer(self) -> FinbertSentimentAnalyzer:
        if self._sentiment is None:
            self._sentiment = FinbertSentimentAnalyzer()
        return self._sentiment

    # ------------------------------------------------------------------
    # Earnings data via yfinance
    # ------------------------------------------------------------------
    def _get_earnings_dates(self, symbol: str) -> Optional[List[dict]]:
        """Fetch earnings dates and EPS data for *symbol* via yfinance.

        Returns a list of dicts sorted by date (most recent first):

            {
                "date": datetime,
                "eps_estimate": float | None,
                "eps_reported": float | None,
                "surprise_pct": float | None,
            }
        """
        try:
            _rate_limit("yfinance", self._last_request)
            ticker = yf.Ticker(symbol)
            df = ticker.earnings_dates
            if df is None or df.empty:
                return None

            results: List[dict] = []
            for idx, row in df.iterrows():
                # idx is a Timestamp with timezone
                earnings_date = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx

                eps_est = row.get("EPS Estimate")
                eps_rep = row.get("Reported EPS")
                surprise = row.get("Surprise(%)")

                # Skip future earnings (no reported EPS yet)
                if eps_rep is None or (isinstance(eps_rep, float) and eps_rep != eps_rep):  # NaN check
                    # Future earnings date — skip for PEAD
                    continue

                results.append({
                    "date": earnings_date,
                    "eps_estimate": float(eps_est) if eps_est is not None and eps_est == eps_est else None,
                    "eps_reported": float(eps_rep) if eps_rep is not None and eps_rep == eps_rep else None,
                    "surprise_pct": float(surprise) if surprise is not None and surprise == surprise else None,
                })

            # Sort by date descending
            results.sort(key=lambda x: x["date"], reverse=True)
            return results if results else None

        except Exception as exc:
            logger.warning("yfinance earnings_dates failed for %s: %s", symbol, exc)
            return None

    def _get_recent_earnings(self, symbol: str, lookback_days: int = 5) -> Optional[dict]:
        """Get the most recent earnings result within *lookback_days*.

        Returns None if no earnings were reported in the window.
        """
        all_earnings = self._get_earnings_dates(symbol)
        if not all_earnings:
            return None

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=lookback_days)

        for entry in all_earnings:
            ed = entry["date"]
            # Make timezone-aware for comparison
            if ed.tzinfo is None:
                ed = ed.replace(tzinfo=timezone.utc)
            if ed >= cutoff and ed <= now:
                return entry
            # If the most recent earnings is too old, stop
            if ed < cutoff:
                break

        return None

    # ------------------------------------------------------------------
    # Transcript fetching (Motley Fool)
    # ------------------------------------------------------------------
    def _find_transcript_url(self, symbol: str, earnings_date: date) -> Optional[str]:
        """Search Motley Fool for the earnings call transcript URL.

        Scans recent transcript pages and matches by ticker.  The Fool
        lists transcripts chronologically so we scan pages backwards from
        the earnings date.
        """
        try:
            # The Fool organises transcripts by date in the URL:
            # /earnings/call-transcripts/YYYY/MM/DD/company-TICKER-qX-YYYY-earnings-transcript/
            # We scan a few pages of the listing and look for matching tickers.
            symbol_lower = symbol.lower().replace(".", "")

            # Determine how many pages to scan based on how long ago earnings was
            days_ago = (date.today() - earnings_date).days
            # Each page has ~20 transcripts, and Fool covers ~20-40/day
            # So 1 page per day roughly
            max_pages = min(days_ago + 3, 15)

            for page in range(0, max_pages + 1):
                if page == 0:
                    # Base URL (most recent transcripts)
                    url = "https://www.fool.com/earnings-call-transcripts/"
                else:
                    url = f"https://www.fool.com/earnings-call-transcripts/page/{page}/"
                _rate_limit("fool_list", self._last_request)

                resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if resp.status_code != 200:
                    continue

                links = list(set(re.findall(r'href="(/earnings/call-transcripts/[^"]+)"', resp.text)))
                for link in links:
                    # Extract ticker from URL: .../company-TICKER-qX-YYYY-earnings-transcript/
                    m = re.search(r"-([a-z]{1,5})-q\d", link)
                    if m and m.group(1) == symbol_lower:
                        full_url = f"https://www.fool.com{link}"
                        # Verify the date roughly matches
                        date_match = re.match(
                            r"/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/", link
                        )
                        if date_match:
                            link_date = date(
                                int(date_match.group(1)),
                                int(date_match.group(2)),
                                int(date_match.group(3)),
                            )
                            # Transcript is usually published same day or next day
                            if abs((link_date - earnings_date).days) <= 3:
                                return full_url
                        else:
                            # No date in URL, accept anyway
                            return full_url

            logger.debug("No Motley Fool transcript found for %s (earnings %s)", symbol, earnings_date)
            return None

        except Exception as exc:
            logger.warning("Transcript search failed for %s: %s", symbol, exc)
            return None

    def _fetch_transcript(self, url: str) -> Optional[str]:
        """Fetch and extract transcript text from a Motley Fool page."""
        try:
            _rate_limit("fool_transcript", self._last_request)
            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if resp.status_code != 200:
                return None

            text = resp.text

            # Remove script and style tags
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)

            # Strategy 1: Look for article-body div (Motley Fool's content container)
            article_match = re.search(
                r'class="article-body[^"]*"[^>]*>(.*?)(?:</div>\s*<div\s+class="(?:article-meta|author)|$)',
                text,
                re.DOTALL | re.I,
            )
            if article_match:
                article_html = article_match.group(1)
            else:
                # Fallback: use the full page
                article_html = text

            # Extract all <p> tag contents — transcripts are structured as paragraphs
            paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", article_html, re.DOTALL | re.I)
            if not paragraphs:
                article_text = _strip_html(article_html)
            else:
                article_text = " ".join(paragraphs)
                article_text = _strip_html(article_text)

            # Trim trailing boilerplate
            end_markers = [
                "The views and opinions expressed",
                "Should you invest $1,000",
                "More From The Motley Fool",
                "This article was",
                "Invest better with The Motley Fool",
                "Making the world smarter",
                "Market data powered by",
                "About The Motley Fool",
            ]
            for marker in end_markers:
                idx = article_text.find(marker)
                if idx > 0:
                    article_text = article_text[:idx].strip()
                    break

            return article_text if len(article_text) > 200 else None

        except Exception as exc:
            logger.warning("Failed to fetch transcript from %s: %s", url, exc)
            return None

    def _get_transcript_qa(self, symbol: str, earnings_date: date) -> Optional[str]:
        """Get the Q&A section of the earnings call transcript.

        Returns the Q&A text or None if no transcript is available.
        """
        # Check cache
        cache_key = f"{symbol}_{earnings_date.isoformat()}"
        if cache_key in self._transcript_cache:
            cached_text, cached_at = self._transcript_cache[cache_key]
            # Cache for 24 hours
            if (datetime.now() - cached_at).total_seconds() < 86400:
                return cached_text

        if not self.fetch_transcripts:
            return None

        url = self._find_transcript_url(symbol, earnings_date)
        if not url:
            self._transcript_cache[cache_key] = (None, datetime.now())
            return None

        transcript = self._fetch_transcript(url)
        if not transcript:
            self._transcript_cache[cache_key] = (None, datetime.now())
            return None

        _, qa_text = _split_qa(transcript)
        if not qa_text:
            # If we can't split, use the whole transcript
            qa_text = transcript

        # Limit to max_transcript_words for performance
        words = qa_text.split()
        if len(words) > self.max_transcript_words:
            qa_text = " ".join(words[: self.max_transcript_words])

        self._transcript_cache[cache_key] = (qa_text, datetime.now())
        return qa_text

    # ------------------------------------------------------------------
    # Sentiment analysis on Q&A
    # ------------------------------------------------------------------
    def _analyze_qa_sentiment(self, qa_text: str) -> dict:
        """Run FinBERT on Q&A text (chunked).

        Returns::

            {
                "sentiment": "positive" | "negative" | "neutral",
                "score": float,           # mean probability of dominant label
                "positive": float,        # mean positive prob
                "negative": float,        # mean negative prob
                "neutral": float,         # mean neutral prob
                "chunks_analyzed": int,
            }
        """
        chunks = _chunk_text(qa_text, max_words=200)
        if not chunks:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 0.0,
                "chunks_analyzed": 0,
            }

        # Run FinBERT on chunks
        results = self.sentiment_analyzer.analyze_headlines(chunks)

        # Aggregate
        agg = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for r in results:
            for label in agg:
                agg[label] += r[label]
            counts[r["sentiment"]] += 1

        n = len(results)
        mean_scores = {k: agg[k] / n for k in agg}

        # Weighted vote: use summed probabilities
        overall = max(mean_scores, key=mean_scores.get)
        overall_score = mean_scores[overall]

        return {
            "sentiment": overall,
            "score": round(overall_score, 4),
            "positive": round(mean_scores["positive"], 4),
            "negative": round(mean_scores["negative"], 4),
            "neutral": round(mean_scores["neutral"], 4),
            "chunks_analyzed": n,
        }

    # ------------------------------------------------------------------
    # PEAD signal generation
    # ------------------------------------------------------------------
    def _generate_pead_signal(
        self,
        symbol: str,
        earnings_entry: dict,
        qa_sentiment: Optional[dict],
    ) -> dict:
        """Generate a PEAD signal from EPS surprise + Q&A sentiment.

        PEAD logic:
        - Positive EPS surprise + positive Q&A → BUY (strong upward drift)
        - Positive EPS surprise + neutral Q&A → BUY (weak)
        - Negative EPS surprise + negative Q&A → AVOID (strong downward drift)
        - Negative EPS surprise + neutral Q&A → AVOID (weak)
        - Neutral surprise: depends on Q&A
        - No transcript: signal based on EPS surprise alone (weaker)
        """
        surprise = earnings_entry.get("surprise_pct")
        eps_est = earnings_entry.get("eps_estimate")
        eps_rep = earnings_entry.get("eps_reported")

        # Determine EPS surprise direction
        eps_positive = False
        eps_negative = False
        if surprise is not None:
            if surprise > 2.0:  # >2% beat
                eps_positive = True
            elif surprise < -2.0:  # >2% miss
                eps_negative = True
        elif eps_est and eps_rep:
            diff = (eps_rep - eps_est) / abs(eps_est) * 100 if eps_est != 0 else 0
            if diff > 2.0:
                eps_positive = True
            elif diff < -2.0:
                eps_negative = True

        # Determine Q&A sentiment direction
        qa_positive = False
        qa_negative = False
        has_transcript = qa_sentiment is not None and qa_sentiment.get("chunks_analyzed", 0) > 0

        if has_transcript:
            qa_sent = qa_sentiment["sentiment"]
            qa_score = qa_sentiment["score"]
            if qa_sent == "positive" and qa_score > 0.5:
                qa_positive = True
            elif qa_sent == "negative" and qa_score > 0.5:
                qa_negative = True

        # PEAD signal matrix
        signal = "NEUTRAL"
        confidence = 0.0
        reasoning_parts: List[str] = []

        if eps_positive and qa_positive:
            signal = "BUY"
            confidence = 0.8
            reasoning_parts.append("positive EPS surprise")
            reasoning_parts.append("positive Q&A sentiment")
        elif eps_positive and has_transcript and not qa_negative:
            signal = "BUY"
            confidence = 0.55
            reasoning_parts.append("positive EPS surprise")
            reasoning_parts.append(f"Q&A sentiment: {qa_sentiment['sentiment']}")
        elif eps_positive and not has_transcript:
            signal = "BUY"
            confidence = 0.4
            reasoning_parts.append("positive EPS surprise (no transcript)")
        elif eps_negative and qa_negative:
            signal = "AVOID"
            confidence = 0.8
            reasoning_parts.append("negative EPS surprise")
            reasoning_parts.append("negative Q&A sentiment")
        elif eps_negative and has_transcript and not qa_positive:
            signal = "AVOID"
            confidence = 0.55
            reasoning_parts.append("negative EPS surprise")
            reasoning_parts.append(f"Q&A sentiment: {qa_sentiment['sentiment']}")
        elif eps_negative and not has_transcript:
            signal = "AVOID"
            confidence = 0.4
            reasoning_parts.append("negative EPS surprise (no transcript)")
        elif has_transcript:
            # Neutral EPS, use Q&A
            if qa_positive:
                signal = "BUY"
                confidence = 0.45
                reasoning_parts.append("neutral EPS surprise")
                reasoning_parts.append("positive Q&A sentiment")
            elif qa_negative:
                signal = "AVOID"
                confidence = 0.45
                reasoning_parts.append("neutral EPS surprise")
                reasoning_parts.append("negative Q&A sentiment")
            else:
                reasoning_parts.append("neutral EPS surprise")
                reasoning_parts.append(f"neutral Q&A sentiment")
        else:
            reasoning_parts.append("no recent earnings surprise")
            reasoning_parts.append("no transcript available")

        # Calculate EPS surprise value
        eps_surprise_val = None
        if surprise is not None:
            eps_surprise_val = round(surprise, 2)
        elif eps_est and eps_rep:
            eps_surprise_val = round(eps_rep - eps_est, 4)

        return {
            "symbol": symbol.upper(),
            "signal": signal,
            "confidence": round(confidence, 2),
            "earnings_date": earnings_entry["date"].strftime("%Y-%m-%d"),
            "eps_estimate": eps_est,
            "eps_reported": eps_rep,
            "eps_surprise": eps_surprise_val,
            "surprise_pct": round(surprise, 2) if surprise is not None else None,
            "qa_sentiment": qa_sentiment if has_transcript else None,
            "reasoning": "; ".join(reasoning_parts),
            "strategy": "PEAD",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_earnings_signals(
        self,
        symbols: List[str],
        lookback_days: int = 5,
    ) -> List[dict]:
        """Get PEAD signals for symbols that recently reported earnings.

        Parameters
        ----------
        symbols : List[str]
            Stock symbols to check.
        lookback_days : int
            How many days back to look for earnings reports (1-5).

        Returns
        -------
        List[dict]
            One dict per symbol that had recent earnings, with keys:
            symbol, signal, confidence, earnings_date, eps_surprise,
            qa_sentiment, reasoning, strategy
        """
        results: List[dict] = []

        for i, symbol in enumerate(symbols, 1):
            logger.info("[%d/%d] Checking earnings for %s ...", i, len(symbols), symbol)

            # Get recent earnings
            recent = self._get_recent_earnings(symbol, lookback_days=lookback_days)
            if not recent:
                logger.debug("  No recent earnings for %s", symbol)
                continue

            logger.info(
                "  %s reported earnings on %s (surprise: %s%%)",
                symbol,
                recent["date"].strftime("%Y-%m-%d"),
                recent.get("surprise_pct"),
            )

            # Get transcript Q&A
            qa_text = self._get_transcript_qa(symbol, recent["date"].date())

            # Analyze Q&A sentiment
            qa_sentiment: Optional[dict] = None
            if qa_text:
                logger.info("  Analyzing Q&A sentiment for %s (%d chars) ...", symbol, len(qa_text))
                qa_sentiment = self._analyze_qa_sentiment(qa_text)
                logger.info(
                    "  %s Q&A: %s (score=%.2f, chunks=%d)",
                    symbol,
                    qa_sentiment["sentiment"],
                    qa_sentiment["score"],
                    qa_sentiment["chunks_analyzed"],
                )
            else:
                logger.info("  No transcript available for %s, using EPS surprise only", symbol)

            # Generate PEAD signal
            signal = self._generate_pead_signal(symbol, recent, qa_sentiment)
            results.append(signal)

        return results

    def get_upcoming_earnings(self, days_ahead: int = 5) -> List[dict]:
        """Fetch upcoming earnings dates for S&P 500 companies.

        Checks each ticker's calendar for upcoming earnings dates within
        the next *days_ahead* days.  Uses yfinance ``ticker.calendar``
        which includes 'Earnings Date'.

        Returns
        -------
        List[dict]
            Sorted by earnings_date ascending:
            {
                "symbol": str,
                "earnings_date": str (ISO),
                "days_until": int,
                "eps_estimate": float | None,
            }
        """
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)
        upcoming: List[dict] = []

        for i, symbol in enumerate(SP500_TOP_TICKERS, 1):
            logger.info("[%d/%d] Checking upcoming earnings for %s ...", i, len(SP500_TOP_TICKERS), symbol)
            try:
                _rate_limit("yfinance", self._last_request)
                ticker = yf.Ticker(symbol)
                cal = ticker.calendar

                if not cal or "Earnings Date" not in cal:
                    continue

                earnings_dates = cal["Earnings Date"]
                if not isinstance(earnings_dates, list):
                    earnings_dates = [earnings_dates]

                for ed in earnings_dates:
                    if isinstance(ed, datetime):
                        ed = ed.date()
                    if today <= ed <= cutoff:
                        days_until = (ed - today).days
                        eps_est = cal.get("Earnings Average")
                        upcoming.append({
                            "symbol": symbol,
                            "earnings_date": ed.isoformat(),
                            "days_until": days_until,
                            "eps_estimate": float(eps_est) if eps_est else None,
                        })
                        logger.info("  %s reports on %s (%d days)", symbol, ed.isoformat(), days_until)

            except Exception as exc:
                logger.debug("  Error checking %s: %s", symbol, exc)

        # Sort by date
        upcoming.sort(key=lambda x: x["earnings_date"])
        return upcoming

    def get_pead_window_signals(
        self,
        symbols: List[str],
        window_days: int = 20,
    ) -> List[dict]:
        """Get PEAD drift signals for stocks that reported in the last
        *window_days* (default 20).

        Unlike ``get_earnings_signals`` which only looks 1-5 days back,
        this looks at the full PEAD drift window (up to 20 days) to find
        stocks still in the drift phase.

        Returns same format as ``get_earnings_signals`` but includes
        ``days_since_earnings`` and ``drift_window_active``.
        """
        results: List[dict] = []

        for i, symbol in enumerate(symbols, 1):
            logger.info("[%d/%d] Checking PEAD window for %s ...", i, len(symbols), symbol)

            all_earnings = self._get_earnings_dates(symbol)
            if not all_earnings:
                continue

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=window_days)

            for entry in all_earnings:
                ed = entry["date"]
                if ed.tzinfo is None:
                    ed = ed.replace(tzinfo=timezone.utc)
                if ed < cutoff or ed > now:
                    continue

                days_since = (now - ed).days

                # Only fetch transcript if earnings was recent (within 7 days)
                # Older earnings won't have easily accessible transcripts
                qa_text = None
                if days_since <= 7:
                    qa_text = self._get_transcript_qa(symbol, ed.date())

                qa_sentiment: Optional[dict] = None
                if qa_text:
                    qa_sentiment = self._analyze_qa_sentiment(qa_text)

                signal = self._generate_pead_signal(symbol, entry, qa_sentiment)
                signal["days_since_earnings"] = days_since
                signal["drift_window_active"] = True
                signal["drift_window_remaining"] = max(0, window_days - days_since)
                results.append(signal)
                break  # Only use most recent earnings

        return results
