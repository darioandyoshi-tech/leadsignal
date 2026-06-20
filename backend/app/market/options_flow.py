#!/usr/bin/env python3
"""Options flow analysis module for LeadSignal.

Tracks unusual options activity to detect institutional positioning.
High call volume = bullish, high put volume = bearish.

Uses yfinance for options chain data (ticker.options, ticker.option_chain).
Attempts to use GammaRips MCP server as an additional data source if available.

References:
  - yfinance options API: https://github.com/ranaroussi/yfinance
  - Max pain theory: price where maximum number of options expire worthless
  - Put/Call ratio: <0.7 bullish, >1.0 bearish (rule of thumb)
  - Unusual volume: volume > N × open interest
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Rate limiting between yfinance API calls (seconds)
YF_RATE_LIMIT_SEC = 0.5

# Signal thresholds for put/call volume ratio
# < 0.7 → BULLISH (call heavy), > 1.3 → BEARISH (put heavy), else NEUTRAL
PCR_BULLISH_THRESHOLD = 0.7
PCR_BEARISH_THRESHOLD = 1.3

# Default volume threshold multiplier for unusual activity
DEFAULT_VOLUME_THRESHOLD = 3.0

# S&P 500 top 50 symbols (by market cap, approximate)
SP500_TOP_50 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK.B",
    "UNH", "XOM", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "CSCO",
    "TMO", "ACN", "ABT", "CRM", "DHR", "TXN", "WFC", "NEE", "PM",
    "UPS", "NKE", "MS", "RTX", "ORCL", "HON", "IBM", "GE", "CAT",
    "BA", "AMGN", "LOW", "SPY", "QQQ",
]


class OptionsFlowScanner:
    """Scans options chains for unusual activity and generates flow signals.

    Parameters
    ----------
    rate_limit_sec : float
        Delay between API calls to avoid rate limiting.
    volume_threshold : float
        Multiplier for unusual volume detection (volume > threshold × OI).
    use_gammarips : bool
        Attempt to use GammaRips MCP server if available.
    """

    def __init__(
        self,
        rate_limit_sec: float = YF_RATE_LIMIT_SEC,
        volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
        use_gammarips: bool = True,
    ) -> None:
        self.rate_limit_sec = rate_limit_sec
        self.volume_threshold = volume_threshold
        self.use_gammarips = use_gammarips
        self._gammarips_available: Optional[bool] = None
        self._last_request_time: float = 0.0

    # ----------------------------------------------------------------------- #
    # Rate limiting
    # ----------------------------------------------------------------------- #

    def _rate_limit(self) -> None:
        """Enforce minimum delay between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_sec:
            time.sleep(self.rate_limit_sec - elapsed)
        self._last_request_time = time.time()

    # ----------------------------------------------------------------------- #
    # GammaRips MCP integration (optional)
    # ----------------------------------------------------------------------- #

    def _check_gammarips(self) -> bool:
        """Check if GammaRips MCP server is accessible.

        Returns True if available, False otherwise.
        """
        if self._gammarips_available is not None:
            return self._gammarips_available
        # GammaRips MCP is not a standard pip package; check for MCP tool availability
        # In practice, this would connect to an MCP server. For now, we attempt
        # a lightweight check and fall back to yfinance.
        try:
            # Check if gammarips MCP client is available in the environment
            import importlib
            spec = importlib.util.find_spec("gammarips")
            if spec is not None:
                self._gammarips_available = True
                logger.info("GammaRips MCP client found")
                return True
        except Exception:
            pass
        self._gammarips_available = False
        logger.info("GammaRips MCP not available — using yfinance only")
        return False

    def _fetch_gammarips_flow(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch options flow from GammaRips MCP server.

        Returns None if not available.
        """
        if not self.use_gammarips or not self._check_gammarips():
            return None
        try:
            # Placeholder for GammaRips MCP integration
            # In production, this would call the MCP server's tools
            # e.g., gammarips.get_order_flow(symbol=symbol)
            logger.debug(f"GammaRips flow fetch for {symbol} (not implemented)")
            return None
        except Exception as e:
            logger.warning(f"GammaRips fetch failed for {symbol}: {e}")
            return None

    # ----------------------------------------------------------------------- #
    # yfinance options data fetching
    # ----------------------------------------------------------------------- #

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        """Create a yfinance Ticker object."""
        return yf.Ticker(symbol)

    def _get_nearest_expiry(self, ticker: yf.Ticker) -> Optional[str]:
        """Get the nearest expiry date for a ticker.

        Returns None if no options data available.
        """
        try:
            expirations = ticker.options
            if not expirations or len(expirations) == 0:
                logger.warning(f"No options expirations found")
                return None
            return expirations[0]
        except Exception as e:
            logger.warning(f"Failed to get expirations: {e}")
            return None

    def _get_option_chain(self, ticker: yf.Ticker, expiry: str) -> Tuple[Any, Any]:
        """Get calls and puts for a given expiry date.

        Returns (calls_df, puts_df).
        """
        chain = ticker.option_chain(expiry)
        return chain.calls, chain.puts

    # ----------------------------------------------------------------------- #
    # Core computation methods
    # ----------------------------------------------------------------------- #

    def _compute_put_call_volume_ratio(self, calls: Any, puts: Any) -> float:
        """Compute put/call volume ratio.

        PCR < 0.7 → bullish (call heavy)
        PCR > 1.3 → bearish (put heavy)
        """
        call_vol = float(calls["volume"].sum()) if "volume" in calls.columns and len(calls) > 0 else 0.0
        put_vol = float(puts["volume"].sum()) if "volume" in puts.columns and len(puts) > 0 else 0.0
        if call_vol == 0:
            return float("inf") if put_vol > 0 else 1.0
        return put_vol / call_vol

    def _compute_put_call_oi_ratio(self, calls: Any, puts: Any) -> float:
        """Compute put/call open interest ratio."""
        call_oi = float(calls["openInterest"].sum()) if "openInterest" in calls.columns and len(calls) > 0 else 0.0
        put_oi = float(puts["openInterest"].sum()) if "openInterest" in puts.columns and len(puts) > 0 else 0.0
        if call_oi == 0:
            return float("inf") if put_oi > 0 else 1.0
        return put_oi / call_oi

    def _compute_max_pain(self, calls: Any, puts: Any) -> float:
        """Compute max pain price.

        Max pain is the strike price at which the total dollar value
        of all options (calls + puts) is minimized (maximum holders expire worthless).

        Returns the max pain strike price.
        """
        if len(calls) == 0 and len(puts) == 0:
            return 0.0

        # Get all unique strikes
        call_strikes = set(calls["strike"].tolist()) if len(calls) > 0 else set()
        put_strikes = set(puts["strike"].tolist()) if len(puts) > 0 else set()
        all_strikes = sorted(call_strikes | put_strikes)

        if not all_strikes:
            return 0.0

        min_pain = float("inf")
        max_pain_strike = all_strikes[0]

        for strike in all_strikes:
            # Cash value for calls: ITM calls (strike < current strike) have intrinsic value
            # Call holders lose money when strike < expiration price
            # For max pain, we calculate total loss to option holders at each expiration price
            call_pain = 0.0
            if len(calls) > 0 and "openInterest" in calls.columns:
                for _, row in calls.iterrows():
                    if strike > row["strike"]:
                        call_pain += (strike - row["strike"]) * float(row.get("openInterest", 0))

            put_pain = 0.0
            if len(puts) > 0 and "openInterest" in puts.columns:
                for _, row in puts.iterrows():
                    if strike < row["strike"]:
                        put_pain += (row["strike"] - strike) * float(row.get("openInterest", 0))

            total_pain = call_pain + put_pain
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = strike

        return float(max_pain_strike)

    def _detect_unusual_options(
        self,
        calls: Any,
        puts: Any,
        volume_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Detect options with volume > threshold × open interest.

        Returns list of unusual activity dicts.
        """
        unusual: List[Dict[str, Any]] = []

        # Check calls
        if len(calls) > 0 and "volume" in calls.columns and "openInterest" in calls.columns:
            for _, row in calls.iterrows():
                vol = float(row.get("volume", 0) or 0)
                oi = float(row.get("openInterest", 0) or 0)
                if oi > 0 and vol > volume_threshold * oi:
                    unusual.append({
                        "type": "CALL",
                        "strike": float(row.get("strike", 0)),
                        "expiry": row.get("expiration", row.get("contractSymbol", "")).split()[-1] if isinstance(row.get("expiration", row.get("contractSymbol", "")), str) else "",
                        "volume": vol,
                        "open_interest": oi,
                        "volume_oi_ratio": round(vol / oi, 2),
                        "last_price": float(row.get("lastPrice", 0) or 0),
                        "implied_volatility": float(row.get("impliedVolatility", 0) or 0),
                        "in_the_money": bool(row.get("inTheMoney", False)),
                    })

        # Check puts
        if len(puts) > 0 and "volume" in puts.columns and "openInterest" in puts.columns:
            for _, row in puts.iterrows():
                vol = float(row.get("volume", 0) or 0)
                oi = float(row.get("openInterest", 0) or 0)
                if oi > 0 and vol > volume_threshold * oi:
                    unusual.append({
                        "type": "PUT",
                        "strike": float(row.get("strike", 0)),
                        "expiry": row.get("expiration", row.get("contractSymbol", "")).split()[-1] if isinstance(row.get("expiration", row.get("contractSymbol", "")), str) else "",
                        "volume": vol,
                        "open_interest": oi,
                        "volume_oi_ratio": round(vol / oi, 2),
                        "last_price": float(row.get("lastPrice", 0) or 0),
                        "implied_volatility": float(row.get("impliedVolatility", 0) or 0),
                        "in_the_money": bool(row.get("inTheMoney", False)),
                    })

        # Sort by volume/OI ratio descending
        unusual.sort(key=lambda x: x["volume_oi_ratio"], reverse=True)
        return unusual

    # ----------------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------------- #

    def get_flow_signal(self, symbol: str) -> Dict[str, Any]:
        """Get options flow signal for a single symbol.

        Fetches options chain for nearest expiry, computes put/call ratios,
        max pain, and unusual options activity.

        Parameters
        ----------
        symbol : str
            Ticker symbol (e.g., "AAPL")

        Returns
        -------
        dict
            {
                "symbol": str,
                "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
                "put_call_volume_ratio": float,
                "put_call_oi_ratio": float,
                "max_pain": float,
                "unusual_calls": int,
                "unusual_puts": int,
                "unusual_activity": list[dict],
                "total_call_volume": float,
                "total_put_volume": float,
                "total_call_oi": float,
                "total_put_oi": float,
                "expiry": str,
                "timestamp": str,
                "details": dict,
            }
        """
        self._rate_limit()

        result: Dict[str, Any] = {
            "symbol": symbol,
            "signal": "NEUTRAL",
            "put_call_volume_ratio": 1.0,
            "put_call_oi_ratio": 1.0,
            "max_pain": 0.0,
            "unusual_calls": 0,
            "unusual_puts": 0,
            "unusual_activity": [],
            "total_call_volume": 0.0,
            "total_put_volume": 0.0,
            "total_call_oi": 0.0,
            "total_put_oi": 0.0,
            "expiry": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {},
            "error": None,
        }

        try:
            ticker = self._get_ticker(symbol)
            expiry = self._get_nearest_expiry(ticker)
            if not expiry:
                result["error"] = "No options data available"
                return result

            calls, puts = self._get_option_chain(ticker, expiry)

            # Compute metrics
            pcr_volume = self._compute_put_call_volume_ratio(calls, puts)
            pcr_oi = self._compute_put_call_oi_ratio(calls, puts)
            max_pain = self._compute_max_pain(calls, puts)
            unusual = self._detect_unusual_options(calls, puts, self.volume_threshold)

            # Count unusual by type
            unusual_calls = sum(1 for u in unusual if u["type"] == "CALL")
            unusual_puts = sum(1 for u in unusual if u["type"] == "PUT")

            # Total volume and OI
            total_call_vol = float(calls["volume"].sum()) if "volume" in calls.columns and len(calls) > 0 else 0.0
            total_put_vol = float(puts["volume"].sum()) if "volume" in puts.columns and len(puts) > 0 else 0.0
            total_call_oi = float(calls["openInterest"].sum()) if "openInterest" in calls.columns and len(calls) > 0 else 0.0
            total_put_oi = float(puts["openInterest"].sum()) if "openInterest" in puts.columns and len(puts) > 0 else 0.0

            # Determine signal
            signal = self._determine_signal(pcr_volume, unusual_calls, unusual_puts)

            # Try GammaRips for additional data
            gammarips_data = self._fetch_gammarips_flow(symbol)

            result.update({
                "signal": signal,
                "put_call_volume_ratio": round(pcr_volume, 4),
                "put_call_oi_ratio": round(pcr_oi, 4),
                "max_pain": round(max_pain, 2),
                "unusual_calls": unusual_calls,
                "unusual_puts": unusual_puts,
                "unusual_activity": unusual[:20],  # Top 20 unusual options
                "total_call_volume": total_call_vol,
                "total_put_volume": total_put_vol,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "expiry": expiry,
                "details": {
                    "num_call_strikes": len(calls),
                    "num_put_strikes": len(puts),
                    "gammarips": gammarips_data,
                },
            })

        except Exception as e:
            logger.error(f"Error getting flow signal for {symbol}: {e}")
            result["error"] = str(e)

        return result

    def _determine_signal(
        self,
        pcr_volume: float,
        unusual_calls: int,
        unusual_puts: int,
    ) -> str:
        """Determine BULLISH/BEARISH/NEUTRAL signal from metrics.

        Combines put/call ratio with unusual activity counts.
        """
        # Start with PCR-based signal
        if pcr_volume < PCR_BULLISH_THRESHOLD:
            signal = "BULLISH"
        elif pcr_volume > PCR_BEARISH_THRESHOLD:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        # Adjust based on unusual activity
        if unusual_calls > unusual_puts and unusual_calls > 0:
            # Heavy unusual call activity is bullish
            if signal == "NEUTRAL":
                signal = "BULLISH"
            elif signal == "BEARISH" and unusual_calls > unusual_puts * 2:
                # Strong call activity overrides bearish PCR
                signal = "NEUTRAL"
        elif unusual_puts > unusual_calls and unusual_puts > 0:
            # Heavy unusual put activity is bearish
            if signal == "NEUTRAL":
                signal = "BEARISH"
            elif signal == "BULLISH" and unusual_puts > unusual_calls * 2:
                # Strong put activity overrides bullish PCR
                signal = "NEUTRAL"

        return signal

    def get_batch_flow_signals(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Get flow signals for multiple symbols with rate limiting.

        Parameters
        ----------
        symbols : List[str]
            List of ticker symbols

        Returns
        -------
        List[dict]
            Results sorted by signal strength (BULLISH first, then NEUTRAL, then BEARISH)
        """
        results: List[Dict[str, Any]] = []
        for i, symbol in enumerate(symbols):
            logger.info(f"Scanning {symbol} ({i+1}/{len(symbols)})...")
            signal = self.get_flow_signal(symbol)
            results.append(signal)

        # Sort by signal strength
        # BULLISH first (lower PCR = more bullish), then NEUTRAL, then BEARISH
        signal_order = {"BULLISH": 0, "NEUTRAL": 1, "BEARISH": 2}
        results.sort(
            key=lambda x: (
                signal_order.get(x.get("signal", "NEUTRAL"), 1),
                x.get("put_call_volume_ratio", 1.0),
            )
        )
        return results

    def get_max_pain(self, symbol: str) -> Dict[str, Any]:
        """Compute max pain price for a symbol.

        Max pain is the strike price where the total dollar value
        of all open options contracts is minimized (most expire worthless).

        Parameters
        ----------
        symbol : str
            Ticker symbol

        Returns
        -------
        dict
            {symbol, max_pain_price, total_call_oi, total_put_oi, expiry}
        """
        self._rate_limit()

        result: Dict[str, Any] = {
            "symbol": symbol,
            "max_pain_price": 0.0,
            "total_call_oi": 0.0,
            "total_put_oi": 0.0,
            "expiry": "",
            "error": None,
        }

        try:
            ticker = self._get_ticker(symbol)
            expiry = self._get_nearest_expiry(ticker)
            if not expiry:
                result["error"] = "No options data available"
                return result

            calls, puts = self._get_option_chain(ticker, expiry)
            max_pain = self._compute_max_pain(calls, puts)

            total_call_oi = float(calls["openInterest"].sum()) if "openInterest" in calls.columns and len(calls) > 0 else 0.0
            total_put_oi = float(puts["openInterest"].sum()) if "openInterest" in puts.columns and len(puts) > 0 else 0.0

            result.update({
                "max_pain_price": round(max_pain, 2),
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "expiry": expiry,
            })

        except Exception as e:
            logger.error(f"Error computing max pain for {symbol}: {e}")
            result["error"] = str(e)

        return result

    def get_unusual_options_activity(
        self,
        symbol: str,
        volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Find options with unusual volume for a symbol.

        Unusual = volume > volume_threshold × open interest.

        Parameters
        ----------
        symbol : str
            Ticker symbol
        volume_threshold : float
            Multiplier threshold (default 3.0× OI)

        Returns
        -------
        List[dict]
            List of unusual activity items sorted by volume/OI ratio
        """
        self._rate_limit()

        try:
            ticker = self._get_ticker(symbol)
            expiry = self._get_nearest_expiry(ticker)
            if not expiry:
                return []

            calls, puts = self._get_option_chain(ticker, expiry)
            return self._detect_unusual_options(calls, puts, volume_threshold)

        except Exception as e:
            logger.error(f"Error getting unusual activity for {symbol}: {e}")
            return []

    def close(self) -> None:
        """Clean up resources."""
        pass