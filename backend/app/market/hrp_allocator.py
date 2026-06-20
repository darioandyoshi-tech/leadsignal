"""Hierarchical Risk Parity (HRP) portfolio allocation.

Uses hierarchical clustering on the correlation matrix of asset returns,
then recursive bisection to allocate risk weights.  More robust than
Markowitz optimisation because it does not require inverting the covariance
matrix — ill-conditioned when the number of assets approaches the number
of observations.

References
----------
De Prado, M. L. (2016). *Building Diversified Portfolios that Outperform
Out of Sample*.  Journal of Portfolio Management, 42(4), 59-69.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────


def _download_prices(symbols: Sequence[str], lookback_days: int) -> pd.DataFrame:
    """Fetch adjusted close prices for *symbols* via yfinance.

    Returns a DataFrame indexed by date with one column per symbol that
    has enough history.  Symbols with insufficient data are silently
    dropped.
    """
    if not symbols:
        return pd.DataFrame()

    cols = list(symbols)
    df = yf.download(
        cols,
        period=f"{lookback_days}d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if df.empty:
        return pd.DataFrame()

    # yfinance returns MultiIndex columns when multiple tickers requested.
    if isinstance(df.columns, pd.MultiIndex):
        try:
            close = df["Close"]
        except KeyError:
            # fallback — take first level
            close = df.xs("Close", level=0, axis=1)
    else:
        close = df

    # Drop columns with too many NaNs (>20% missing)
    min_obs = int(len(close) * 0.8)
    close = close.dropna(axis=1, thresh=min_obs)

    # Forward-fill remaining small gaps, then drop rows that are all-NaN
    close = close.ffill().dropna(how="all")

    return close


def _correlation_distance(corr: pd.DataFrame) -> pd.DataFrame:
    """Distance metric from correlation:  d = sqrt(0.5 * (1 - corr))."""
    return np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))


def _get_quasi_diag(link) -> List[int]:
    """Return the ordered leaf indices from a scipy linkage matrix."""
    # to_tree needs a float linkage matrix; keep a float copy
    link_float = link.astype(float)
    tree = to_tree(link_float, rd=False)
    order = tree.pre_order()
    return order


def _get_ivp(cov: np.ndarray) -> np.ndarray:
    """Inverse-variance portfolio weights for a covariance sub-matrix."""
    ivp = 1.0 / np.diag(cov)
    ivp /= ivp.sum()
    return ivp


def _get_cluster_var(cov: np.ndarray, w: np.ndarray) -> float:
    """Cluster variance:  w' Σ w."""
    return float(w @ cov @ w)


def _recursive_bisection(cov: np.ndarray, sorted_indices: List[int]) -> np.ndarray:
    """Recursively bisect the sorted asset list and allocate IVP weights."""
    return _recursive_bisection_impl(cov, sorted_indices)


def _recursive_bisection_impl(cov: np.ndarray, sorted_indices: List[int]) -> np.ndarray:
    n = len(sorted_indices)
    w = np.ones(n)

    # Use a queue of index-lists
    from collections import deque

    queue = deque([sorted_indices])

    while queue:
        indices = queue.popleft()
        if len(indices) <= 1:
            continue

        split = len(indices) // 2
        left = indices[:split]
        right = indices[split:]

        # Covariance sub-matrices
        cov_left = cov[np.ix_(left, left)]
        cov_right = cov[np.ix_(right, right)]

        w_left = _get_ivp(cov_left)
        w_right = _get_ivp(cov_right)

        var_left = _get_cluster_var(cov_left, w_left)
        var_right = _get_cluster_var(cov_right, w_right)

        alpha = 1.0 - var_left / (var_left + var_right)

        # Scale weights in the parent cluster
        # We need a mapping from global index to position in `sorted_indices`
        # Actually, we work with positions in the sorted array.
        # `indices` are positions in the original covariance matrix.
        # We maintain `w` indexed by position in `sorted_indices`.

        # Map original index -> position in sorted_indices
        pos_map = {idx: pos for pos, idx in enumerate(sorted_indices)}

        for i in left:
            w[pos_map[i]] *= alpha
        for i in right:
            w[pos_map[i]] *= (1.0 - alpha)

        queue.append(left)
        queue.append(right)

    return w


# ── main class ──────────────────────────────────────────────────────────────


class HRPAllocator:
    """Hierarchical Risk Parity portfolio allocator.

    Parameters
    ----------
    max_weight : float, optional
        Maximum weight any single asset can receive (concentration cap).
        Applied *after* HRP optimisation by redistribating excess weight.
    """

    def __init__(self, max_weight: Optional[float] = None):
        self.max_weight = max_weight

    # ── public API ─────────────────────────────────────────────────────────

    def allocate(
        self,
        symbols: List[str],
        lookback_days: int = 60,
    ) -> Dict[str, float]:
        """Compute HRP weights for *symbols*.

        Returns a dict mapping each valid symbol to its weight (sums to 1.0).
        Symbols with insufficient price history are silently excluded.
        """
        if not symbols:
            return {}

        # 1. Fetch prices
        prices = _download_prices(symbols, lookback_days)
        if prices.empty or prices.shape[1] < 2:
            # Not enough assets for clustering — fall back to equal weight
            valid = [s for s in symbols if s in prices.columns] if not prices.empty else []
            if not valid:
                logger.warning("HRP: no valid price data for %s", symbols)
                return {}
            w = 1.0 / len(valid)
            return {s: round(w, 6) for s in valid}

        # 2. Daily returns
        returns = prices.pct_change().dropna(how="all").dropna(axis=0)
        if returns.shape[0] < 5:
            logger.warning("HRP: insufficient return observations (%d)", returns.shape[0])
            valid = list(prices.columns)
            w = 1.0 / len(valid)
            return {s: round(w, 6) for s in valid}

        # 3. Covariance & correlation
        cov = returns.cov()
        corr = returns.corr()

        # Replace NaNs (can happen if a column is constant)
        cov = cov.fillna(cov.median().median() if cov.size else 1.0)
        corr = corr.fillna(0.0)
        np.fill_diagonal(corr.values, 1.0)

        # 4. Distance matrix and linkage
        dist = _correlation_distance(corr)
        # Ensure diagonal is zero and matrix is symmetric
        np.fill_diagonal(dist.values, 0.0)
        dist = (dist + dist.T) / 2.0

        # Convert to condensed form for linkage
        condensed = squareform(dist.values, checks=False)

        if len(condensed) == 0:
            # Single asset or degenerate case
            valid = list(prices.columns)
            w = 1.0 / len(valid)
            return {s: round(w, 6) for s in valid}

        link = linkage(condensed, method="single")

        # 5. Quasi-diagonalisation
        sorted_idx = _get_quasi_diag(link)

        # 6. Recursive bisection
        cov_vals = cov.values
        raw_weights = _recursive_bisection_impl(cov_vals, sorted_idx)

        # Map back to column names (sorted_indices are column positions in the cov matrix)
        columns = list(cov.columns)
        weights = {columns[sorted_idx[i]]: raw_weights[i] for i in range(len(sorted_idx))}

        # Normalise
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        # Apply concentration cap
        if self.max_weight:
            weights = self._apply_cap(weights)

        # Round and return
        weights = {k: round(v, 6) for k, v in weights.items()}

        logger.info(
            "HRP allocated %d symbols (lookback=%d): top=%s",
            len(weights),
            lookback_days,
            max(weights, key=weights.get) if weights else "N/A",
        )
        return weights

    def get_position_sizes(
        self,
        symbols: List[str],
        total_capital: float,
        lookback_days: int = 60,
    ) -> Dict[str, float]:
        """Dollar allocation per symbol based on HRP weights."""
        weights = self.allocate(symbols, lookback_days=lookback_days)
        return {s: round(w * total_capital, 2) for s, w in weights.items()}

    def get_max_position_per_symbol(
        self,
        symbols: List[str],
        max_pct: float = 0.25,
        lookback_days: int = 60,
    ) -> Dict[str, float]:
        """Maximum dollar position per symbol if *total_capital* were 1.

        Returns weights with each capped at *max_pct*.  Useful for
        concentration-limit checks; multiply by actual capital externally.
        """
        self.max_weight = max_pct
        weights = self.allocate(symbols, lookback_days=lookback_days)
        self.max_weight = None  # reset
        return weights

    # ── internal ────────────────────────────────────────────────────────────

    def _apply_cap(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Redistribute any weight above *max_weight* to uncapped assets."""
        cap = self.max_weight
        if cap is None or cap <= 0:
            return weights

        weights = dict(weights)
        for _ in range(100):  # safety limit
            over = {k: v for k, v in weights.items() if v > cap}
            if not over:
                break
            excess = sum(v - cap for v in over.values())
            for k in over:
                weights[k] = cap
            # Distribute excess to uncapped assets proportionally
            under = {k: v for k, v in weights.items() if v < cap}
            if not under:
                break
            under_total = sum(under.values())
            if under_total <= 0:
                break
            for k in under:
                weights[k] += excess * (weights[k] / under_total)
        return weights


# ── convenience ─────────────────────────────────────────────────────────────


def build_hrp_allocation(symbols: List[str], lookback_days: int = 60) -> Dict[str, float]:
    """One-shot helper: allocate weights for *symbols* using HRP."""
    allocator = HRPAllocator()
    return allocator.allocate(symbols, lookback_days=lookback_days)