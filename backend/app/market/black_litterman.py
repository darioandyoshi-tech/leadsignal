#!/usr/bin/env python3
"""Black-Litterman portfolio optimization with vendor alpha views.

Combines market equilibrium returns with our active views (vendor incident
alpha, insider signals, sentiment) to produce adjusted portfolio weights.

The Black-Litterman model:
1. Start with market equilibrium (implied returns from market cap weights)
2. Add our active views (e.g., "CRM will underperform due to Cloudflare incident")
3. Blend the two based on view confidence
4. Optimize the blended expected returns with risk constraints

This gives us a systematic way to translate our alpha signals into
portfolio position sizes, rather than ad-hoc filtering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import yfinance as yf
from datetime import datetime, timedelta


@dataclass
class BLView:
    """A single Black-Litterman view."""
    symbol: str
    direction: str  # "over" or "under"
    expected_return: float  # expected annualized return delta (e.g., -0.05 for -5%)
    confidence: float  # 0-1, how confident we are in this view
    source: str  # "vendor_alpha", "insider", "sentiment", etc.
    reasoning: str


class BlackLittermanOptimizer:
    """Black-Litterman portfolio optimizer with active views.

    Usage:
        bl = BlackLittermanOptimizer()
        views = [
            BLView("CRM", "under", -0.05, 0.7, "vendor_alpha", "Cloudflare incident"),
            BLView("AAPL", "over", 0.03, 0.5, "insider", "Cluster buy"),
        ]
        weights = bl.optimize(views, symbols=["AAPL", "MSFT", "CRM", ...])
    """

    def __init__(self, lookback_days: int = 252, risk_free_rate: float = 0.04, tau: float = 0.025):
        self.lookback_days = lookback_days
        self.risk_free_rate = risk_free_rate
        self.tau = tau  # uncertainty scaling for prior

    def _fetch_price_data(self, symbols: List[str]) -> pd.DataFrame:
        """Fetch adjusted close prices for all symbols."""
        end = datetime.utcnow().date()
        start = end - timedelta(days=self.lookback_days)
        data = yf.download(symbols, start=start, end=end + timedelta(days=1),
                           auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            closes = data["Close"]
        else:
            closes = data[["Close"]].rename(columns={"Close": symbols[0]})
            closes.columns = symbols
        return closes.dropna(axis=1, how="all")

    def _compute_equilibrium_returns(self, closes: pd.DataFrame) -> pd.Series:
        """Compute implied equilibrium returns from market weights.

        Simplified: use inverse variance as proxy for market weights,
        then compute implied returns as: lambda * Sigma * w_market
        """
        returns = closes.pct_change().dropna()
        cov = returns.cov() * 252  # annualized

        # Market cap weights proxy: equal weight (can be enhanced with real market caps)
        n = len(cov)
        w_market = np.ones(n) / n

        # Risk aversion coefficient
        risk_aversion = (0.08 - self.risk_free_rate) / np.dot(w_market, np.dot(cov, w_market))

        # Implied equilibrium returns
        pi = risk_aversion * cov.values @ w_market
        return pd.Series(pi, index=cov.index)

    def _build_view_matrix(self, views: List[BLView], symbols: List[str]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build P (view matrix), Q (view returns), Omega (view uncertainty)."""
        n = len(symbols)
        k = len(views)
        sym_idx = {s: i for i, s in enumerate(symbols)}

        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)

        for i, view in enumerate(views):
            if view.symbol in sym_idx:
                P[i, sym_idx[view.symbol]] = 1.0 if view.direction == "over" else -1.0
                Q[i] = abs(view.expected_return)
                # Omega: uncertainty proportional to view confidence
                # Higher confidence → smaller Omega → more weight on view
                omega_diag[i] = (1 - view.confidence) * 0.01  # scale: 0-1% variance

        Omega = np.diag(omega_diag) if k > 0 else np.zeros((0, 0))
        return P, Q, Omega

    def optimize(
        self,
        views: List[BLView],
        symbols: List[str],
        max_weight: float = 0.25,
        min_weight: float = 0.0,
    ) -> Dict[str, float]:
        """Run Black-Litterman optimization and return portfolio weights.

        Args:
            views: List of BLView objects with our active alpha signals
            symbols: List of S&P 500 symbols to include
            max_weight: Maximum weight per symbol (concentration limit)
            min_weight: Minimum weight per symbol

        Returns:
            Dict mapping symbol to weight (sums to 1.0)
        """
        # Filter to symbols with data
        closes = self._fetch_price_data(symbols)
        available = list(closes.columns)
        if len(available) < 2:
            # Not enough data, return equal weights
            return {s: 1.0 / len(symbols) for s in symbols}

        # Filter views to available symbols
        active_views = [v for v in views if v.symbol in available]

        # Compute equilibrium returns (prior)
        pi = self._compute_equilibrium_returns(closes)
        cov = closes.pct_change().dropna().cov() * 252
        Sigma = cov.values

        # Build view matrices
        P, Q, Omega = self._build_view_matrix(active_views, available)

        # Black-Litterman formula:
        # E[R] = pi + tau*Sigma * P' * (P * tau*Sigma * P' + Omega)^-1 * (Q - P*pi)
        tau_sigma = self.tau * Sigma

        if len(active_views) > 0:
            middle = P @ tau_sigma @ P.T + Omega
            middle_inv = np.linalg.pinv(middle)
            posterior_returns = pi.values + tau_sigma @ P.T @ middle_inv @ (Q - P @ pi.values)
        else:
            posterior_returns = pi.values

        # Optimize weights using posterior returns
        # Simple approach: proportional to return/risk ratio
        posterior_series = pd.Series(posterior_returns, index=available)
        vol = pd.Series(np.sqrt(np.diag(Sigma)), index=available)

        # Sharpe-like weight: return / vol, then normalize
        raw_weights = posterior_series / vol
        raw_weights = raw_weights.clip(lower=0)  # no short positions

        # Apply max/min weight constraints
        total = raw_weights.sum()
        if total > 0:
            weights = raw_weights / total
        else:
            weights = pd.Series(1.0 / len(available), index=available)

        # Enforce max weight constraint
        weights = weights.clip(upper=max_weight)
        # Re-normalize after clipping
        total = weights.sum()
        if total > 0:
            weights = weights / total

        # Enforce min weight (set below min to 0, re-normalize)
        weights[weights < min_weight * 0.5] = 0
        total = weights.sum()
        if total > 0:
            weights = weights / total

        return {s: round(float(weights.get(s, 0)), 4) for s in symbols}

    def views_from_vendor_signals(self, vendor_signals: List[dict]) -> List[BLView]:
        """Convert vendor incident alpha signals to BL views."""
        views = []
        for signal in vendor_signals:
            for sym in signal.get("affected_symbols", []):
                # Negative view: expect underperformance
                severity = signal.get("incident_severity", "minor")
                conf = signal.get("confidence", 0.5)

                expected_impact = -0.03 if severity == "critical" else -0.02 if severity == "major" else -0.01

                views.append(BLView(
                    symbol=sym,
                    direction="under",
                    expected_return=expected_impact,
                    confidence=conf,
                    source="vendor_alpha",
                    reasoning=f"{signal.get('vendor_name', 'Unknown')} incident: {signal.get('incident_title', '')}",
                ))
        return views

    def views_from_insider_signals(self, insider_signals: List[dict]) -> List[BLView]:
        """Convert insider trading signals to BL views."""
        views = []
        for signal in insider_signals:
            sym = signal.get("symbol")
            if not sym:
                continue

            sig_type = signal.get("signal", "")
            cluster = signal.get("cluster_count", 1)

            if "STRONG_BUY" in sig_type:
                views.append(BLView(sym, "over", 0.04, 0.7, "insider",
                                    f"Cluster buy: {cluster} insiders buying"))
            elif "BUY" in sig_type:
                views.append(BLView(sym, "over", 0.02, 0.5, "insider",
                                    f"Insider buy: {cluster} insiders"))
            elif "STRONG_SELL" in sig_type:
                views.append(BLView(sym, "under", -0.04, 0.7, "insider",
                                    f"Cluster sell: {cluster} insiders selling"))
            elif "SELL" in sig_type:
                views.append(BLView(sym, "under", -0.02, 0.5, "insider",
                                    f"Insider sell: {cluster} insiders"))
        return views


if __name__ == "__main__":
    # Quick test
    bl = BlackLittermanOptimizer(lookback_days=60)
    views = [
        BLView("CRM", "under", -0.05, 0.7, "vendor_alpha", "Cloudflare incident"),
        BLView("AAPL", "over", 0.03, 0.5, "insider", "Cluster buy"),
        BLView("MSFT", "over", 0.02, 0.4, "congressional", "Committee member buy"),
    ]
    symbols = ["AAPL", "MSFT", "CRM", "NVDA", "AMZN", "GOOGL", "META", "NFLX"]
    weights = bl.optimize(views, symbols)
    print("Black-Litterman weights:")
    for sym, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {sym}: {w:.2%} ({w*10000:.0f} bps)")
    print(f"  Total: {sum(weights.values()):.2%}")