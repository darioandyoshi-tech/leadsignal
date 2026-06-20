#!/usr/bin/env python3
"""Tensor Network (Matrix Product State) time series analyzer.

Uses Matrix Product State (MPS) / tensor train decomposition to model the
joint distribution of multi-stock daily returns.  Unlike TimesFM and TFT
which forecast individual series, this module captures *inter-stock*
higher-order correlations by compressing the N-body return distribution
tensor into a chain of small matrices connected by bond edges.

Key ideas
---------
* Each stock's daily return is discretised into a small alphabet of bins
  (e.g. {-2σ,-1σ,0,+1σ,+2σ}) so that the joint distribution of N stocks
  over one day lives in a tensor of shape (d, d, …, d) — d^N entries.
* An MPS / tensor-train approximation replaces that exponentially large
  tensor with N small core tensors linked by bond indices of size at most
  ``bond_dim``.
* SVD-based compression (alternating least squares / simple sequential SVD)
  is used to find the cores.
* Entanglement entropy of the MPS bond between two halves of the chain
  serves as a systemic-risk score: high entropy ⇒ stocks are tightly
  coupled ⇒ diversification breaks down in stress periods.
* Correlation clusters are extracted from the mutual information matrix
  computed from pairs of cores.

Usage
-----
    from app.market.tensor_network import TensorNetworkAnalyzer

    tna = TensorNetworkAnalyzer()
    info = tna.fit(["AAPL","MSFT","AMZN","NVDA","META",
                    "JPM","V","UNH","HD","DIS"], lookback_days=252, bond_dim=8)
    pred = tna.predict_joint(recent_returns)
    risk = tna.get_systemic_risk_score()
    clusters = tna.get_correlation_clusters()
    bt = tna.backtest(symbols, lookback_days=252, hold_days=4)
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.linalg import svd

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [TensorNet] %(message)s")
log = logging.getLogger("tensor_network")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_returns(symbols: List[str], lookback_days: int) -> pd.DataFrame:
    """Fetch daily simple returns for *symbols* via yfinance."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback_days * 2)  # extra room for holidays
    data = yf.download(
        symbols, start=start, end=end + timedelta(days=1),
        auto_adjust=True, progress=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        closes = data["Close"]
    else:
        closes = data[["Close"]].rename(columns={"Close": symbols[0]})
        closes.columns = symbols
    closes = closes.dropna(axis=1, how="all").dropna()
    # align columns to requested order, drop missing
    available = [s for s in symbols if s in closes.columns]
    closes = closes[available]
    returns = closes.pct_change().dropna()
    return returns


def _discretise(returns: pd.DataFrame, n_bins: int = 5) -> np.ndarray:
    """Discretise each column into *n_bins* quantile bins, return int array.

    Returns array shape (T, N) with values in [0, n_bins-1].
    """
    T, N = returns.shape
    codes = np.zeros((T, N), dtype=int)
    for j in range(N):
        col = returns.iloc[:, j].values
        # Use quantile-based binning so each bin has roughly equal mass
        percentiles = np.linspace(0, 100, n_bins + 1)
        edges = np.percentile(col, percentiles)
        # Ensure unique edges (degenerate for small ranges)
        edges = np.unique(edges)
        if len(edges) < n_bins + 1:
            # Fall back to equal-width
            edges = np.linspace(col.min(), col.min() + 1e-8 + (col.max() - col.min()), n_bins + 1)
        codes[:, j] = np.searchsorted(edges[1:-1], col, side="right")
        codes[:, j] = np.clip(codes[:, j], 0, n_bins - 1)
    return codes


# ---------------------------------------------------------------------------
# MPS construction
# ---------------------------------------------------------------------------

def _build_joint_tensor(codes: np.ndarray, n_bins: int, smoothing: Optional[float] = None) -> np.ndarray:
    """Build empirical joint distribution tensor from discretised codes.

    A Dirichlet smoothing prior is added to every entry so the tensor is
    not pathologically sparse.  With only T≈252 observations and d^N ≈ 9.7 M
    entries the raw empirical tensor is almost entirely zero, so a small
    floor per entry helps the MPS capture correlation structure.

    If *smoothing* is None a per-entry prior of ``1e-6`` is used — large
    enough to avoid zeros but small enough to not drown the signal.

    Returns a tensor of shape (n_bins, n_bins, ..., n_bins) with N axes
    (one per stock), normalised to sum 1.
    """
    T, N = codes.shape
    shape = (n_bins,) * N
    if smoothing is None:
        smoothing = 1e-6
    tensor = np.full(shape, smoothing, dtype=np.float64)
    for t in range(T):
        idx = tuple(int(codes[t, j]) for j in range(N))
        tensor[idx] += 1.0
    tensor /= tensor.sum()
    return tensor


def _mps_decompose(tensor: np.ndarray, bond_dim: int) -> Tuple[List[np.ndarray], float]:
    """Tensor-train / MPS decomposition via sequential SVD.

    Parameters
    ----------
    tensor : np.ndarray
        N-way joint distribution tensor, shape (d, d, ..., d).
    bond_dim : int
        Maximum bond dimension (truncation).

    Returns
    -------
    cores : list of np.ndarray
        List of N core tensors.  Core i has shape (r_left, d, r_right).
    fit_loss : float
        Relative Frobenius error of the reconstruction vs the original.
    """
    ndim = tensor.ndim
    d = tensor.shape[0]
    # We work with a residual tensor that we progressively split.
    # Shape evolves: left_bond × remaining_dims
    reshaped = tensor.copy().astype(np.float64)
    cores: List[np.ndarray] = []
    left_bond = 1

    for i in range(ndim - 1):
        # Reshape: (left_bond * d) × (d^(remaining-1))
        remaining = reshaped.size // (left_bond * d)
        mat = reshaped.reshape(left_bond * d, remaining)
        U, S, Vt = svd(mat, full_matrices=False)
        # Truncate to bond_dim
        chi = min(bond_dim, len(S))
        U = U[:, :chi]
        S = S[:chi]
        Vt = Vt[:chi, :]
        # Core i: shape (left_bond, d, chi)
        core = U.reshape(left_bond, d, chi)
        cores.append(core)
        # Update residual
        reshaped = (np.diag(S) @ Vt).reshape((chi,) + tensor.shape[i + 1:])
        left_bond = chi

    # Last core: (left_bond, d, 1)
    last = reshaped.reshape(left_bond, d, 1)
    cores.append(last)

    # --- compute reconstruction error ---
    recon = _mps_reconstruct(cores)
    fit_loss = float(np.linalg.norm(tensor - recon) / max(np.linalg.norm(tensor), 1e-12))
    return cores, fit_loss


def _mps_reconstruct(cores: List[np.ndarray]) -> np.ndarray:
    """Reconstruct full tensor from MPS cores (for error checking)."""
    result = cores[0]  # shape (1, d, r1)
    for c in cores[1:]:
        # contract last bond of result with first bond of c
        r_left = result.shape[-1]
        d = c.shape[1]
        r_right = c.shape[2]
        # result shape: (..., r_left), c shape: (r_left, d, r_right)
        result = np.tensordot(result, c, axes=(-1, 0))  # shape (..., d, r_right)
    # squeeze trailing 1s
    return np.squeeze(result, axis=(0, -1)) if result.ndim > len(cores) else np.squeeze(result)


# ---------------------------------------------------------------------------
# Entanglement entropy
# ---------------------------------------------------------------------------

def _entanglement_entropy(cores: List[np.ndarray], site: Optional[int] = None) -> float:
    """Von Neumann entanglement entropy across bond at *site*.

    Splits the MPS chain at the bond between core *site* and *site+1*
    and computes the entropy of the singular values there.
    """
    N = len(cores)
    if site is None:
        site = N // 2  # middle cut
    if site < 0 or site >= N - 1:
        return 0.0
    # The bond dimension lives in cores[site].shape[2] == cores[site+1].shape[0]
    # Reconstruct the Schmidt values by contracting the left and right halves
    # and doing an SVD on the reshaped bond.
    # Simpler: the singular values were already stored implicitly. We
    # re-derive them from the contraction.
    # Left half contraction → shape (1, ..., r)
    left = cores[0]
    for i in range(1, site + 1):
        left = np.tensordot(left, cores[i], axes=(-1, 0))
    # left shape: (d, d, ..., r_left)  with leading 1s
    left = left.reshape(-1, left.shape[-1])  # (anything, r_left)
    right = cores[site + 1]
    for i in range(site + 2, N):
        right = np.tensordot(right, cores[i], axes=(-1, 0))
    # right shape: (r_right, d, ..., 1)
    right = right.reshape(right.shape[0], -1)  # (r_right, anything)
    # M = left @ right  → (anything_l, anything_r) — not what we want.
    # We need the SVD of the *wavefunction* viewed as a matrix of
    # (left_partition × right_partition).  The Schmidt values are the
    # singular values of that matrix.
    # left is (L, r), right is (r, R) → wavefunction = left @ right (L, R)
    wave = left @ right  # shape (L, R)
    # SVD of wave gives Schmidt values
    try:
        s = svd(wave, compute_uv=False)
    except Exception:
        return 0.0
    s = s[s > 1e-12]
    if len(s) == 0:
        return 0.0
    probs = s ** 2
    probs = probs / probs.sum()
    entropy = -np.sum(probs * np.log2(probs + 1e-15))
    return float(entropy)


# ---------------------------------------------------------------------------
# Mutual information between sites
# ---------------------------------------------------------------------------

def _pairwise_mutual_info(cores: List[np.ndarray], n_bins: int) -> np.ndarray:
    """Compute an N×N mutual information matrix from the MPS.

    For each pair (i, j) we contract the chain to get the 2-marginal
    P(b_i, b_j), then compute MI = H(b_i) + H(b_j) - H(b_i, b_j).

    The contraction is done by building left and right environment tensors
    and then contracting only the two target cores' physical indices.
    """
    N = len(cores)
    d = cores[0].shape[1]

    # Pre-compute left and right environments for every cut position.
    # left_envs[k]  = contraction of cores[0..k-1] with all physical indices
    #                  summed out → shape (r_k,)
    # right_envs[k] = contraction of cores[k+1..N-1] → shape (r_k,)
    left_envs = [np.ones(1)]  # left_envs[0] = scalar 1
    for k in range(N - 1):
        core = cores[k]  # (r_left, d, r_right)
        # Sum physical index
        summed = core.sum(axis=1)  # (r_left, r_right)
        left_envs.append(left_envs[-1] @ summed)  # (r_right,)

    right_envs = [np.ones(1)] * N  # right_envs[N-1] = scalar 1
    for k in range(N - 1, 0, -1):
        core = cores[k]
        summed = core.sum(axis=1)  # (r_left, r_right)
        right_envs[k - 1] = summed @ right_envs[k]  # (r_left,)

    # Single-site marginals
    marginals = []
    for i in range(N):
        core = cores[i]  # (r_left, d, r_right)
        m = np.einsum('l,ldr,r->d', left_envs[i], core, right_envs[i])
        total = m.sum()
        if total > 1e-15:
            m = m / total
        else:
            m = np.ones(d) / d
        marginals.append(m)

    # Pairwise marginals and MI
    mi = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1, N):
            # Contract all cores between i and j (summing physical indices)
            # to get a transfer matrix from bond after i to bond before j
            if j == i + 1:
                transfer = np.eye(cores[i].shape[2])  # identity if adjacent
            else:
                transfer = None
                for k in range(i + 1, j):
                    core = cores[k]
                    summed = core.sum(axis=1)  # (r_left, r_right)
                    if transfer is None:
                        transfer = summed
                    else:
                        transfer = transfer @ summed
                if transfer is None:
                    transfer = np.eye(cores[i].shape[2])

            # Contract: left_env[i] @ core_i[:, :, :] @ transfer @ core_j[:, :, :] @ right_env[j]
            # Result: sum over bonds, keep physical indices i and j
            core_i = cores[i]  # (r_li, d, r_ri)
            core_j = cores[j]  # (r_lj, d, r_rj)

            # Step 1: left_env[i] @ core_i → (d, r_ri)
            tmp = np.einsum('l,ldr->dr', left_envs[i], core_i)
            # Step 2: @ transfer → (d, r_lj)  [r_ri == r_lj of next, but transfer connects r_ri to r_lj]
            tmp = tmp @ transfer  # (d, r_lj)
            # Step 3: @ core_j → (d, d, r_rj) → then @ right_env[j] → (d, d)
            joint2 = np.einsum('dr,rds,s->dd', tmp, core_j, right_envs[j])

            total = joint2.sum()
            if total > 1e-15:
                joint2 = joint2 / total
            else:
                joint2 = np.ones((d, d)) / (d * d)

            p_i = marginals[i].reshape(-1, 1)
            p_j = marginals[j].reshape(1, -1)
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = joint2 / (p_i * p_j + 1e-15)
                mi_val = float(np.sum(joint2 * np.log2(ratio + 1e-15)))
            mi[i, j] = max(mi_val, 0.0)
            mi[j, i] = mi[i, j]
    return mi


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TensorNetworkAnalyzer:
    """Matrix Product State (MPS) analyser for multi-stock correlations.

    The MPS compresses the N-body return distribution tensor into a chain
    of small tensors, capturing higher-order (not just pairwise) dependencies
    between stocks.
    """

    def __init__(self, n_bins: int = 5):
        self.n_bins = n_bins
        self.cores: Optional[List[np.ndarray]] = None
        self.symbols: Optional[List[str]] = None
        self.returns_df: Optional[pd.DataFrame] = None
        self.codes: Optional[np.ndarray] = None
        self.joint_tensor: Optional[np.ndarray] = None
        self.bond_dim: int = 8
        self.fit_loss: float = 1.0
        self._bin_centers: Optional[np.ndarray] = None  # (N, n_bins) representative return values

    # -- fitting ----------------------------------------------------------

    def fit(self, symbols: List[str], lookback_days: int = 252, bond_dim: int = 8) -> dict:
        """Fit the MPS to the joint return distribution of *symbols*.

        Parameters
        ----------
        symbols : list of str
            Tickers to model jointly.
        lookback_days : int
            History window in calendar days.
        bond_dim : int
            Maximum MPS bond dimension (controls compression vs accuracy).

        Returns
        -------
        dict with keys: symbols, bond_dim, compression_ratio, fit_loss
        """
        log.info("Fetching %d symbols, lookback=%d days", len(symbols), lookback_days)
        returns = _fetch_returns(symbols, lookback_days)
        # Align symbols to what we actually got
        fitted_symbols = list(returns.columns)
        if len(fitted_symbols) < 2:
            raise ValueError(f"Need at least 2 symbols with data, got {len(fitted_symbols)}")

        N = len(fitted_symbols)
        d = self.n_bins

        # Discretise returns into bins
        codes = _discretise(returns, n_bins=d)
        self._bin_centers = np.zeros((N, d))
        for j in range(N):
            col = returns.iloc[:, j].values
            percentiles = np.linspace(0, 100, d + 1)
            edges = np.percentile(col, percentiles)
            edges = np.unique(edges)
            if len(edges) < d + 1:
                edges = np.linspace(col.min(), col.max() + 1e-8, d + 1)
            for b in range(d):
                lo = edges[b]
                hi = edges[b + 1]
                mask = (col >= lo) & (col < hi) if b < d - 1 else (col >= lo)
                self._bin_centers[j, b] = col[mask].mean() if mask.any() else (lo + hi) / 2

        # Build joint distribution tensor
        log.info("Building %d-body joint tensor (d=%d, N=%d)", d, d, N)
        joint = _build_joint_tensor(codes, d)
        self.joint_tensor = joint

        # MPS decomposition
        log.info("Running MPS decomposition, bond_dim=%d", bond_dim)
        cores, fit_loss = _mps_decompose(joint, bond_dim)
        self.cores = cores
        self.symbols = fitted_symbols
        self.returns_df = returns
        self.codes = codes
        self.bond_dim = bond_dim
        self.fit_loss = fit_loss

        # Compression ratio: full tensor size vs total MPS parameters
        full_size = d ** N
        mps_size = sum(c.size for c in cores)
        compression_ratio = full_size / max(mps_size, 1)

        log.info(
            "MPS fit complete: N=%d, bond_dim=%d, fit_loss=%.4f, compression=%.1fx",
            N, bond_dim, fit_loss, compression_ratio,
        )

        return {
            "symbols": fitted_symbols,
            "bond_dim": bond_dim,
            "compression_ratio": round(compression_ratio, 2),
            "fit_loss": round(fit_loss, 4),
        }

    # -- prediction -------------------------------------------------------

    def predict_joint(self, recent_returns: np.ndarray) -> np.ndarray:
        """Predict next-day returns for all fitted symbols given recent returns.

        Uses the fitted MPS to compute a conditional expectation:
        E[r_{t+1} | recent_returns] for each symbol.

        Parameters
        ----------
        recent_returns : np.ndarray, shape (N,) or (window, N)
            Recent daily returns for the fitted symbols.  If (window, N),
            the last row is used.

        Returns
        -------
        np.ndarray of shape (N,) — expected next-day return per symbol.
        """
        if self.cores is None or self._bin_centers is None or self.symbols is None:
            raise RuntimeError("Call fit() before predict_joint()")

        recent = np.asarray(recent_returns, dtype=np.float64)
        if recent.ndim == 2:
            recent = recent[-1]  # use most recent row
        N = len(self.symbols)
        if recent.shape[0] != N:
            raise ValueError(f"recent_returns has {recent.shape[0]} values, expected {N}")

        d = self.n_bins
        # Discretise each symbol's recent return into the closest bin
        bin_idx = np.zeros(N, dtype=int)
        for j in range(N):
            bin_idx[j] = np.argmin(np.abs(self._bin_centers[j] - recent[j]))

        # For each symbol j, compute conditional expected return given
        # all other symbols are fixed at their observed bins.
        # E[r_j | others] = sum_b bin_centers[j,b] * P(b | others)
        # P(b | others) ∝ joint(b, bin_idx[others]) — the marginal
        # obtained by fixing all physical indices except j.

        predicted = np.zeros(N)
        for j in range(N):
            # Contract the MPS with all sites fixed except j
            # This gives a vector of length d: the unnormalised probabilities
            probs = self._conditional_probabilities(j, bin_idx)
            expected = np.dot(probs, self._bin_centers[j])
            predicted[j] = expected

        return predicted

    def _conditional_probabilities(self, target_site: int, bin_idx: np.ndarray) -> np.ndarray:
        """Compute P(site=target | other sites fixed) from the MPS.

        Returns a probability vector of length n_bins.
        """
        if self.cores is None:
            raise RuntimeError("MPS not fitted")
        N = len(self.cores)
        d = self.n_bins

        # Contract left-to-right, then right-to-left, keeping the target site open
        # Left environments: L[0] = (1,), L[k] = contraction of cores[0..k-1]
        # with physical indices fixed to bin_idx
        left_env = np.ones(1)  # bond 0 is size 1
        for k in range(target_site):
            core = self.cores[k]  # (r_left, d, r_right)
            # Fix physical index to bin_idx[k]
            fixed = core[:, bin_idx[k], :]  # (r_left, r_right)
            left_env = left_env @ fixed  # (r_left_new,)

        # Right environments from the right side
        right_env = np.ones(1)
        for k in range(N - 1, target_site, -1):
            core = self.cores[k]  # (r_left, d, r_right)
            fixed = core[:, bin_idx[k], :]  # (r_left, r_right)
            # fixed is (r_left, r_right), right_env is (r_right,)
            # result: (r_left, r_right) @ (r_right,) → (r_left,)
            right_env = fixed @ right_env

        # Target core: (r_left, d, r_right)
        target_core = self.cores[target_site]
        # Contract left_env with left bond, right_env with right bond
        # left_env shape (r_left,), right_env shape (r_right,)
        probs = np.zeros(d)
        for b in range(d):
            probs[b] = left_env @ target_core[:, b, :] @ right_env
        # Normalise
        total = probs.sum()
        if total > 1e-15:
            probs = probs / total
        else:
            probs = np.ones(d) / d
        return probs

    # -- systemic risk -----------------------------------------------------

    def get_systemic_risk_score(self) -> float:
        """Compute systemic risk from MPS entanglement entropy.

        High entanglement entropy → stocks are highly coupled → systemic risk.
        Low entanglement → stocks are independent → diversification works.

        Returns a float in [0, log2(bond_dim)].
        """
        if self.cores is None:
            raise RuntimeError("MPS not fitted")
        # Average entanglement entropy across all bonds
        N = len(self.cores)
        if N < 2:
            return 0.0
        entropies = []
        for site in range(N - 1):
            e = _entanglement_entropy(self.cores, site)
            entropies.append(e)
        avg_entropy = float(np.mean(entropies))
        # Normalise to [0, 1] by dividing by log2(bond_dim)
        max_entropy = np.log2(self.bond_dim) if self.bond_dim > 1 else 1.0
        return float(min(avg_entropy / max_entropy, 1.0))

    # -- correlation clusters ----------------------------------------------

    def get_correlation_clusters(self) -> List[List[str]]:
        """Identify clusters of highly correlated stocks from the MPS.

        Combines MPS-derived mutual information with the empirical return
        correlation matrix and uses a simple threshold-based connected-
        components clustering.
        """
        if self.cores is None or self.symbols is None:
            raise RuntimeError("MPS not fitted")
        N = len(self.cores)
        if N < 2:
            return [[self.symbols[0]]] if self.symbols else []

        # Empirical correlation matrix (robust signal)
        corr = self.returns_df.corr().values if self.returns_df is not None else np.eye(N)

        # MPS mutual information (higher-order signal, may be noisy)
        mi = _pairwise_mutual_info(self.cores, self.n_bins)

        # Normalise MI to [0, 1] range — use max of off-diagonal entries
        mi_offdiag = mi.copy()
        np.fill_diagonal(mi_offdiag, 0.0)
        mi_max = np.nanmax(mi_offdiag)
        if mi_max > 0 and np.isfinite(mi_max):
            mi_norm = np.nan_to_num(mi / mi_max, nan=0.0)
        else:
            mi_norm = np.zeros_like(mi)
        np.fill_diagonal(mi_norm, 0.0)

        # Blend: 60% correlation, 40% normalised MI
        # Correlation captures linear dependence, MI captures non-linear
        # and higher-order dependencies from the MPS.
        corr_abs = np.abs(corr)
        blend = 0.6 * corr_abs + 0.4 * mi_norm
        np.fill_diagonal(blend, 0.0)
        blend = np.nan_to_num(blend, nan=0.0)

        # Threshold: 75th percentile of blended scores
        upper = blend[np.triu_indices(N, k=1)]
        upper = upper[np.isfinite(upper)]
        if len(upper) > 0:
            threshold = float(np.percentile(upper, 75))
        else:
            threshold = 0.3
        threshold = max(threshold, 0.3)

        # Connected components via adjacency
        adjacency = blend > threshold
        visited = [False] * N
        clusters: List[List[str]] = []
        for i in range(N):
            if visited[i]:
                continue
            # BFS
            queue = [i]
            cluster = []
            while queue:
                node = queue.pop()
                if visited[node]:
                    continue
                visited[node] = True
                cluster.append(self.symbols[node])
                for j in range(N):
                    if not visited[j] and adjacency[node, j]:
                        queue.append(j)
            clusters.append(cluster)

        # Sort clusters by size (largest first)
        clusters.sort(key=len, reverse=True)
        return clusters

    # -- backtest ----------------------------------------------------------

    def backtest(self, symbols: List[str], lookback_days: int = 252, hold_days: int = 4) -> dict:
        """Backtest MPS-based stock selection vs equal-weight baseline.

        Strategy:
        1. Fit MPS on the first *lookback_days* of data.
        2. Each trading day: use recent returns to predict joint next-day returns.
        3. Pick top 5 stocks by predicted return, equal-weight them.
        4. Hold for *hold_days* days, then rebalance.
        5. Compare against equal-weight baseline (all symbols, rebalanced same frequency).

        Returns
        -------
        dict with: mps_return, baseline_return, mps_sharpe, baseline_sharpe, hit_rate
        """
        log.info("Backtest: %d symbols, lookback=%d, hold=%d", len(symbols), lookback_days, hold_days)
        returns = _fetch_returns(symbols, lookback_days + 260)  # extra for OOS
        fitted_symbols = list(returns.columns)
        if len(fitted_symbols) < 5:
            raise ValueError(f"Need at least 5 symbols, got {len(fitted_symbols)}")

        N = len(fitted_symbols)
        T = len(returns)
        d = self.n_bins

        # Split: first 252 rows for fit, rest for OOS
        fit_end = min(252, T - hold_days - 10)
        oos_start = fit_end
        oos_returns = returns.iloc[oos_start:].values
        fit_returns = returns.iloc[:fit_end]

        if len(oos_returns) < hold_days * 2:
            return {
                "mps_return": 0.0, "baseline_return": 0.0,
                "mps_sharpe": 0.0, "baseline_sharpe": 0.0,
                "hit_rate": 0.0, "note": "Insufficient OOS data",
            }

        # Fit MPS on the training portion
        codes_fit = _discretise(fit_returns, n_bins=d)
        joint_fit = _build_joint_tensor(codes_fit, d)
        cores, fit_loss = _mps_decompose(joint_fit, self.bond_dim)
        self.cores = cores
        self.symbols = fitted_symbols
        self.returns_df = fit_returns
        self.codes = codes_fit
        self.joint_tensor = joint_fit
        self.fit_loss = fit_loss
        self._bin_centers = np.zeros((N, d))
        for j in range(N):
            col = fit_returns.iloc[:, j].values
            percentiles = np.linspace(0, 100, d + 1)
            edges = np.percentile(col, percentiles)
            edges = np.unique(edges)
            if len(edges) < d + 1:
                edges = np.linspace(col.min(), col.max() + 1e-8, d + 1)
            for b in range(d):
                lo = edges[b]
                hi = edges[b + 1]
                mask = (col >= lo) & (col < hi) if b < d - 1 else (col >= lo)
                self._bin_centers[j, b] = col[mask].mean() if mask.any() else (lo + hi) / 2

        # Walk-forward backtest
        mps_portfolio_returns = []
        baseline_portfolio_returns = []
        hits = 0
        total_periods = 0

        oos_T = len(oos_returns)
        t = 0
        while t + hold_days < oos_T:
            # Recent returns = last row of available history (t-1 in oos, but
            # we have the fit_returns before oos_start)
            if t == 0:
                recent = fit_returns.iloc[-1].values
            else:
                recent = oos_returns[t - 1]

            # Predict joint next-day returns
            predicted = self.predict_joint(recent)

            # Top 5 by predicted return
            top_k = min(5, N)
            top_idx = np.argsort(predicted)[::-1][:top_k]
            top_weights = np.zeros(N)
            top_weights[top_idx] = 1.0 / top_k

            # Baseline: equal weight all
            baseline_weights = np.ones(N) / N

            # Realised returns over hold period
            realised = oos_returns[t: t + hold_days]  # (hold_days, N)
            mps_period = realised @ top_weights  # (hold_days,)
            baseline_period = realised @ baseline_weights

            mps_portfolio_returns.extend(mps_period)
            baseline_portfolio_returns.extend(baseline_period)

            # Hit rate: did MPS beat baseline over this hold period?
            if mps_period.sum() > baseline_period.sum():
                hits += 1
            total_periods += 1
            t += hold_days

        mps_arr = np.array(mps_portfolio_returns)
        baseline_arr = np.array(baseline_portfolio_returns)

        mps_return = float(np.prod(1 + mps_arr) - 1)
        baseline_return = float(np.prod(1 + baseline_arr) - 1)

        # Annualised Sharpe (daily freq, 252 trading days)
        mps_sharpe = float(
            np.mean(mps_arr) / (np.std(mps_arr) + 1e-10) * np.sqrt(252)
        ) if len(mps_arr) > 1 else 0.0
        baseline_sharpe = float(
            np.mean(baseline_arr) / (np.std(baseline_arr) + 1e-10) * np.sqrt(252)
        ) if len(baseline_arr) > 1 else 0.0

        hit_rate = float(hits / max(total_periods, 1))

        log.info(
            "Backtest done: MPS=%.4f (%.2f Sharpe), baseline=%.4f (%.2f Sharpe), hit_rate=%.2f",
            mps_return, mps_sharpe, baseline_return, baseline_sharpe, hit_rate,
        )

        return {
            "mps_return": round(mps_return, 4),
            "baseline_return": round(baseline_return, 4),
            "mps_sharpe": round(mps_sharpe, 2),
            "baseline_sharpe": round(baseline_sharpe, 2),
            "hit_rate": round(hit_rate, 2),
        }


# ---------------------------------------------------------------------------
# CLI / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tensor Network (MPS) analyzer smoke test")
    parser.add_argument("--symbols", nargs="+",
                        default=["AAPL", "MSFT", "AMZN", "NVDA", "META",
                                 "JPM", "V", "UNH", "HD", "DIS"])
    parser.add_argument("--lookback", type=int, default=252)
    parser.add_argument("--bond-dim", type=int, default=8)
    parser.add_argument("--backtest", action="store_true", help="Run backtest too")
    args = parser.parse_args()

    tna = TensorNetworkAnalyzer()
    info = tna.fit(args.symbols, lookback_days=args.lookback, bond_dim=args.bond_dim)
    print("\n=== Fit Info ===")
    for k, v in info.items():
        print(f"  {k}: {v}")

    # Predict using last available returns
    last_returns = tna.returns_df.iloc[-1].values
    pred = tna.predict_joint(last_returns)
    print("\n=== Predicted Next-Day Returns ===")
    for sym, p in zip(tna.symbols, pred):
        print(f"  {sym}: {p:+.5f}")

    # Systemic risk
    risk = tna.get_systemic_risk_score()
    print(f"\n=== Systemic Risk Score: {risk:.4f} (0=diversified, 1=coupled)")

    # Correlation clusters
    clusters = tna.get_correlation_clusters()
    print("\n=== Correlation Clusters ===")
    for i, cl in enumerate(clusters):
        print(f"  Cluster {i+1}: {cl}")

    if args.backtest:
        bt = tna.backtest(args.symbols, lookback_days=args.lookback, hold_days=4)
        print("\n=== Backtest ===")
        for k, v in bt.items():
            print(f"  {k}: {v}")