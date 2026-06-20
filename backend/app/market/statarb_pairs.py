"""Statistical arbitrage pairs trading module.

Scans S&P 500 for cointegrated equity pairs using the Engle-Granger test,
computes spread z-scores, generates mean-reversion signals, and backtests
the pairs strategy.

The core idea: if two stocks are cointegrated, their spread is stationary
and mean-reverts.  We trade deviations from the mean:

- **Entry** (z > 2): short the overperformer, long the underperformer
- **Exit**  (z < 0.5): spread reverted to mean → close position
- **Stop**  (z > 4): divergence too far → cut losses

"""

from __future__ import annotations

import logging
import math
from typing import List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from statsmodels.tsa.stattools import coint, adfuller

logger = logging.getLogger("statarb_pairs")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ENTRY_Z = 2.0       # |z| above this → enter
EXIT_Z = 0.5        # |z| below this → exit
STOP_Z = 4.0        # |z| above this → stop out
COINT_PVALUE = 0.05  # significance threshold


class PairsTrader:
    """Find cointegrated pairs and generate pairs-trading signals."""

    # ---- entry/exit/stop thresholds (class-level for easy override) ----
    entry_z: float = ENTRY_Z
    exit_z: float = EXIT_Z
    stop_z: float = STOP_Z
    coint_pvalue: float = COINT_PVALUE

    # ------------------------------------------------------------------
    #  Data fetching
    # ------------------------------------------------------------------
    @staticmethod
    def _fetch_prices(symbols: List[str], lookback_days: int) -> pd.DataFrame:
        """Fetch adjusted close prices for *symbols* over *lookback_days*.

        Returns a DataFrame indexed by date with one column per symbol.
        """
        end = pd.Timestamp.now(tz="UTC").tz_convert("America/New_York").date()
        start = end - pd.Timedelta(days=lookback_days + 10)  # extra buffer for holidays

        # yfinance batch download
        tickers_str = " ".join(symbols)
        df = yf.download(
            tickers_str,
            start=start,
            end=end + pd.Timedelta(days=1),
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        if df.empty:
            return pd.DataFrame()

        # Extract just Close prices — yfinance returns MultiIndex columns
        # when downloading multiple tickers with group_by='ticker'
        if isinstance(df.columns, pd.MultiIndex):
            # Columns: (ticker, field) — pick Close for each ticker
            close = df.xs("Close", level=1, axis=1)
        else:
            # Single ticker or flat columns
            if "Close" in df.columns:
                close = df[["Close"]].copy()
                close.columns = [symbols[0]]
            else:
                close = df.copy()

        # Ensure column names match symbols (yfinance may reorder)
        if len(symbols) > 1:
            available = [s for s in symbols if s in close.columns]
            close = close[available]

        close.index = pd.to_datetime(close.index).tz_localize(None)
        close = close.dropna(how="all")
        return close

    # ------------------------------------------------------------------
    #  Cointegration scanning
    # ------------------------------------------------------------------
    def find_cointegrated_pairs(
        self,
        symbols: List[str],
        lookback_days: int = 252,
        max_pairs: int = 200,
    ) -> List[dict]:
        """Scan *symbols* for cointegrated pairs via Engle-Granger test.

        Parameters
        ----------
        symbols : list of ticker strings
        lookback_days : price history window (default 252 = 1 year)
        max_pairs : cap on number of pairs to test (for performance; 0 = all)

        Returns
        -------
        list of dicts:
            {symbol_a, symbol_b, p_value, hedge_ratio, half_life,
             spread_mean, spread_std}
        """
        prices = self._fetch_prices(symbols, lookback_days)
        if prices.empty:
            logger.error("No price data returned")
            return []

        # Drop columns with too many NaNs (use actual row count, not lookback_days)
        min_obs = max(50, int(len(prices) * 0.8))
        good_cols = prices.columns[prices.notna().sum() >= min_obs]
        prices = prices[list(good_cols)]
        prices = prices.dropna()

        if len(prices.columns) < 2:
            logger.error("Need at least 2 symbols with data")
            return []

        cols = list(prices.columns)
        n = len(cols)
        pairs_found: List[dict] = []
        pairs_tested = 0

        for i in range(n):
            for j in range(i + 1, n):
                if max_pairs and pairs_tested >= max_pairs:
                    break
                sym_a, sym_b = cols[i], cols[j]
                series_a = prices[sym_a].values
                series_b = prices[sym_b].values

                # Need equal length, non-constant
                if len(series_a) < 60 or np.std(series_a) == 0 or np.std(series_b) == 0:
                    pairs_tested += 1
                    continue

                try:
                    # Engle-Granger cointegration test
                    score, p_value, crit_values = coint(series_a, series_b)
                except Exception as exc:
                    logger.debug("coint failed %s/%s: %s", sym_a, sym_b, exc)
                    pairs_tested += 1
                    continue

                if p_value >= self.coint_pvalue:
                    pairs_tested += 1
                    continue

                # OLS hedge ratio: series_a = hedge_ratio * series_b + intercept
                X = np.column_stack([np.ones(len(series_b)), series_b])
                coeffs = np.linalg.lstsq(X, series_a, rcond=None)[0]
                hedge_ratio = float(coeffs[1])

                # Spread = A - hedge_ratio * B
                spread = series_a - hedge_ratio * series_b
                spread_mean = float(np.mean(spread))
                spread_std = float(np.std(spread))
                if spread_std == 0:
                    pairs_tested += 1
                    continue

                half_life = self._compute_half_life(spread)

                pairs_found.append({
                    "symbol_a": sym_a,
                    "symbol_b": sym_b,
                    "p_value": float(p_value),
                    "hedge_ratio": hedge_ratio,
                    "half_life": half_life,
                    "spread_mean": spread_mean,
                    "spread_std": spread_std,
                })
                pairs_tested += 1

            if max_pairs and pairs_tested >= max_pairs:
                break

        # Sort by p-value (most cointegrated first)
        pairs_found.sort(key=lambda p: p["p_value"])
        logger.info("Found %d cointegrated pairs from %d tested", len(pairs_found), pairs_tested)
        return pairs_found

    # ------------------------------------------------------------------
    #  Signal generation
    # ------------------------------------------------------------------
    def get_pair_signals(self, pairs: List[dict]) -> List[dict]:
        """Compute current z-score signals for each pair.

        Returns
        -------
        list of dicts:
            {symbol_a, symbol_b, z_score, signal, hedge_ratio}
        """
        if not pairs:
            return []

        # Fetch recent prices for all involved symbols
        all_symbols = sorted(set(
            s for p in pairs for s in (p["symbol_a"], p["symbol_b"])
        ))
        prices = self._fetch_prices(all_symbols, 60)  # 60 days enough for z-score
        if prices.empty:
            logger.error("No price data for signals")
            return []

        signals: List[dict] = []
        for p in pairs:
            sym_a, sym_b = p["symbol_a"], p["symbol_b"]
            if sym_a not in prices.columns or sym_b not in prices.columns:
                continue

            pa = prices[sym_a].dropna()
            pb = prices[sym_b].dropna()
            # Align
            common = pa.index.intersection(pb.index)
            if len(common) < 5:
                continue
            pa = pa.loc[common]
            pb = pb.loc[common]

            hedge_ratio = p["hedge_ratio"]
            spread = pa - hedge_ratio * pb
            current_spread = float(spread.iloc[-1])

            spread_mean = p["spread_mean"]
            spread_std = p["spread_std"]
            if spread_std == 0:
                continue

            z_score = (current_spread - spread_mean) / spread_std
            z = float(z_score)

            # Determine signal
            if abs(z) >= self.stop_z:
                signal = "STOP"
            elif abs(z) >= self.entry_z:
                if z > 0:
                    # A overpriced, B underpriced
                    signal = "ENTER_SHORT_A_LONG_B"
                else:
                    # B overpriced, A underpriced
                    signal = "ENTER_SHORT_B_LONG_A"
            elif abs(z) <= self.exit_z:
                signal = "EXIT"
            else:
                signal = "HOLD"

            signals.append({
                "symbol_a": sym_a,
                "symbol_b": sym_b,
                "z_score": round(z, 4),
                "spread": round(current_spread, 4),
                "signal": signal,
                "hedge_ratio": round(hedge_ratio, 4),
                "p_value": round(p["p_value"], 6),
                "half_life": round(p["half_life"], 1) if p.get("half_life") else None,
            })

        return signals

    # ------------------------------------------------------------------
    #  Backtesting
    # ------------------------------------------------------------------
    def backtest_pair(
        self,
        symbol_a: str,
        symbol_b: str,
        lookback_days: int = 252,
    ) -> dict:
        """Backtest a single pair strategy.

        Walks through history day-by-day, entering/Exiting/stopping based
        on z-score.  Returns performance metrics.
        """
        prices = self._fetch_prices([symbol_a, symbol_b], lookback_days)
        if prices.empty or symbol_a not in prices.columns or symbol_b not in prices.columns:
            return {"error": "No price data"}

        df = prices[[symbol_a, symbol_b]].dropna()
        if len(df) < 60:
            return {"error": "Insufficient data"}

        # Estimate hedge ratio on first 80% of data
        split = int(len(df) * 0.8)
        train = df.iloc[:split]
        test = df.iloc[split:]

        if len(train) < 30:
            return {"error": "Insufficient training data"}

        # OLS hedge ratio
        X = np.column_stack([np.ones(len(train)), train[symbol_b].values])
        coeffs = np.linalg.lstsq(X, train[symbol_a].values, rcond=None)[0]
        hedge_ratio = float(coeffs[1])

        spread_train = train[symbol_a] - hedge_ratio * train[symbol_b]
        spread_mean = float(spread_train.mean())
        spread_std = float(spread_train.std())
        if spread_std == 0:
            return {"error": "Zero spread std"}

        # Walk through test period
        position = 0  # 0=flat, 1=short A long B, -1=long A short B
        entry_idx = 0
        returns_list: List[float] = []
        trades: List[dict] = []

        for i in range(len(test)):
            row = test.iloc[i]
            spread = row[symbol_a] - hedge_ratio * row[symbol_b]
            z = (spread - spread_mean) / spread_std

            # P&L if in position
            if position != 0 and i > 0:
                prev = test.iloc[i - 1]
                # Daily return of spread
                spread_ret = (spread - prev_spread) / (abs(hedge_ratio) * prev[symbol_b] + prev[symbol_a]) * 2
                # Apply direction
                daily_ret = spread_ret * position
                returns_list.append(daily_ret)

            prev_spread = spread

            # Signal logic
            if position == 0:
                if abs(z) >= self.stop_z:
                    pass  # don't enter on stop
                elif z > self.entry_z:
                    position = 1  # short A, long B
                    entry_idx = i
                    trades.append({"action": "ENTER_SHORT_A_LONG_B", "z": round(z, 2), "day": i})
                elif z < -self.entry_z:
                    position = -1  # long A, short B
                    entry_idx = i
                    trades.append({"action": "ENTER_SHORT_B_LONG_A", "z": round(z, 2), "day": i})
            else:
                if abs(z) >= self.stop_z:
                    trades.append({"action": "STOP", "z": round(z, 2), "day": i, "held": i - entry_idx})
                    position = 0
                elif abs(z) <= self.exit_z:
                    trades.append({"action": "EXIT", "z": round(z, 2), "day": i, "held": i - entry_idx})
                    position = 0

        # Close any open position at end
        if position != 0 and trades:
            trades.append({"action": "EXIT_EOD", "day": len(test) - 1, "held": len(test) - 1 - entry_idx})

        # Compute metrics
        if not returns_list:
            return {
                "symbol_a": symbol_a,
                "symbol_b": symbol_b,
                "total_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "num_trades": len(trades),
                "win_rate": 0.0,
            }

        returns_arr = np.array(returns_list)
        cumulative = np.cumprod(1 + returns_arr)
        total_return = float(cumulative[-1] - 1)

        # Sharpe (annualised, 252 trading days)
        if np.std(returns_arr) > 0:
            sharpe = float(np.mean(returns_arr) / np.std(returns_arr) * math.sqrt(252))
        else:
            sharpe = 0.0

        # Max drawdown
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

        # Win rate
        completed_trades = [t for t in trades if t["action"] in ("EXIT", "STOP", "EXIT_EOD")]
        if completed_trades:
            # Approximate win: held > 0 and exit not stop
            wins = sum(1 for t in completed_trades if t["action"] == "EXIT")
            win_rate = wins / len(completed_trades)
        else:
            win_rate = 0.0

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "hedge_ratio": round(hedge_ratio, 4),
            "total_return": round(total_return, 4),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 4),
            "num_trades": len(trades),
            "win_rate": round(win_rate, 4),
        }

    # ------------------------------------------------------------------
    #  Correlation matrix
    # ------------------------------------------------------------------
    def get_correlation_matrix(
        self,
        symbols: List[str],
        lookback_days: int = 60,
        window: int = 20,
    ) -> pd.DataFrame:
        """Return a rolling-correlation matrix for diversification checks.

        Uses a *window*-day rolling correlation, returning the latest
        correlation snapshot between all symbol pairs.
        """
        prices = self._fetch_prices(symbols, lookback_days)
        if prices.empty:
            return pd.DataFrame()

        prices = prices.dropna(how="all")
        returns = prices.pct_change().dropna()

        if returns.empty:
            return pd.DataFrame()

        # Rolling correlation (last window)
        rolling_corr = returns.rolling(window).corr()
        if rolling_corr.empty:
            return pd.DataFrame()

        # Take the last snapshot
        last_date = returns.index[-1]
        corr_snapshot = rolling_corr.loc[last_date]
        if isinstance(corr_snapshot, pd.DataFrame):
            return corr_snapshot
        return pd.DataFrame()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_half_life(spread: np.ndarray) -> float:
        """Estimate half-life of mean reversion via Ornstein-Uhlenbeck.

        Regress Δspread_t on spread_{t-1}:
            Δspread_t = α + λ * spread_{t-1} + ε
        Half-life = -ln(2) / λ
        """
        try:
            spread_lag = spread[:-1]
            spread_diff = np.diff(spread)
            X = np.column_stack([np.ones(len(spread_diff)), spread_lag])
            coeffs = np.linalg.lstsq(X, spread_diff, rcond=None)[0]
            lam = float(coeffs[1])
            if lam >= 0:
                return float("inf")
            half_life = -math.log(2) / lam
            return float(half_life)
        except Exception:
            return float("inf")


# ---------------------------------------------------------------------------
#  S&P 500 top symbols helper
# ---------------------------------------------------------------------------
def get_sp500_top_symbols(n: int = 100) -> List[str]:
    """Return the top *n* S&P 500 symbols by market cap (curated list).

    This uses a curated list of large-cap S&P 500 components suitable
    for pairs scanning.  For a live list, use ``fetch_sp500_symbols``
    from the fetcher module.
    """
    # Top 100 by market cap (approximate, as of recent)
    top_symbols = [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK.B",
        "LLY", "AVGO", "TSLA", "JPM", "V", "UNH", "XOM", "WMT", "MA",
        "JNJ", "PG", "HD", "COST", "ORCL", "ABBV", "MRK", "CVX", "NFLX",
        "BAC", "AMD", "CRM", "ADBE", "KO", "PEP", "TMO", "CSCO", "ACN",
        "ABT", "DHR", "TXN", "WFC", "LIN", "PM", "UPS", "INTC", "MS",
        "LOW", "SPGI", "INTU", "SYK", "NEE", "TJX", "RTX", "HON", "IBM",
        "AMGN", "CAT", "GE", "ISRG", "GD", "MDLZ", "AXP", "GS", "BLK",
        "DE", "BKNG", "ADP", "GILD", "ADSK", "VRTX", "PGR", "PLD", "MMC",
        "CI", "MET", "BMY", "MSI", "SCHW", "PYPL", "MO", "C", "ZTS",
        "CB", "REGN", "LMT", "TGT", "PFE", "DUK", "SO", "CL", "EOG",
        "PSX", "MPC", "OXY", "FDX", "ITW", "AON", "TRV", "USB", "FIS",
        "CME", "SHW", "FDX", "EMR", "APD", "NSC", "AIG", "WM", "MCK",
    ]
    # Deduplicate
    seen = set()
    result = []
    for s in top_symbols:
        if s not in seen and len(result) < n:
            seen.add(s)
            result.append(s)
    return result[:n]