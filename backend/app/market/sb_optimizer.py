"""Simulated Bifurcation (SB) portfolio optimizer.

Implements the discrete simulated bifurcation algorithm (dSB) developed by
Toshiba (Goto et al., Sci. Adv. 2019, 2021) for solving combinatorial portfolio
optimisation as a QUBO problem.  The algorithm uses symplectic Euler
integration of a classical Hamiltonian system with adiabatic pumping of a
bifurcation parameter, running entirely on classical hardware (no quantum
processor required).

References
----------
[1] Goto, H. et al., "Combinatorial optimization by simulating adiabatic
    bifurcations in nonlinear Hamiltonian systems", Sci. Adv. 5, eaav2372 (2019).
[2] Goto, H. et al., "High-performance combinatorial optimization based on
    classical mechanics", Sci. Adv. 7, eabe7953 (2021).
[3] Kanao, T., Goto, H., "Simulated bifurcation assisted by thermal
    fluctuation", Commun Phys 5, 153 (2022).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default hyper-parameters
# ---------------------------------------------------------------------------
DEFAULT_STEPS = 10_000
DEFAULT_DT = 0.15
DEFAULT_AGENTS = 64  # parallel oscillators (multi-agent search)
DEFAULT_PRESSURE_SLOPE = 0.005  # adiabatic pumping rate
DEFAULT_PENALTY = 1e3  # cardinality constraint penalty
RISK_FREE_RATE = 0.04 / 252  # daily risk-free ~4 % annual


class SimulatedBifurcationOptimizer:
    """Quantum-inspired portfolio optimizer using the discrete SB algorithm.

    The portfolio selection problem (pick *K* of *N* assets to maximise
    risk-adjusted return) is encoded as a QUBO and solved with dSB.
    """

    def __init__(
        self,
        steps: int = DEFAULT_STEPS,
        dt: float = DEFAULT_DT,
        agents: int = DEFAULT_AGENTS,
        pressure_slope: float = DEFAULT_PRESSURE_SLOPE,
        penalty: float = DEFAULT_PENALTY,
        seed: int | None = 42,
    ) -> None:
        self.steps = steps
        self.dt = dt
        self.agents = agents
        self.pressure_slope = pressure_slope
        self.penalty = penalty
        self.rng = np.random.default_rng(seed)
        self.seed = seed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def optimize_portfolio(
        self,
        symbols: List[str],
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        num_select: int = 5,
        risk_aversion: float = 1.0,
    ) -> dict:
        """Optimise a cardinality-constrained portfolio via SB.

        Parameters
        ----------
        symbols : list of str
            Asset tickers (length *N*).
        expected_returns : np.ndarray, shape (N,)
            Expected return per asset (daily mean).
        cov_matrix : np.ndarray, shape (N, N)
            Covariance matrix of daily returns.
        num_select : int
            Cardinality – how many assets to pick.
        risk_aversion : float
            Penalty on variance (higher = more risk-averse).

        Returns
        -------
        dict with keys:
            ``selected_symbols``, ``weights``, ``expected_return``,
            ``risk``, ``sharpe_ratio``
        """
        n = len(symbols)
        if expected_returns.shape[0] != n or cov_matrix.shape != (n, n):
            raise ValueError("Dimension mismatch between symbols, returns, and cov_matrix")
        if num_select > n or num_select < 1:
            raise ValueError(f"num_select must be in [1, {n}], got {num_select}")

        expected_returns = np.asarray(expected_returns, dtype=np.float64)
        cov_matrix = np.asarray(cov_matrix, dtype=np.float64)

        # 1. Build QUBO  (minimisation form)
        Q = self._build_qubo(expected_returns, cov_matrix, num_select, risk_aversion)

        # 2. Run SB  (multiple restarts, keep best)
        best_x = None
        best_energy = np.inf
        for _ in range(5):  # 5 restarts with different random init
            x = self._run_sb(Q)
            energy = float(x @ Q @ x)
            if energy < best_energy:
                best_energy = energy
                best_x = x

        x = best_x

        # 3. Repair: enforce cardinality if SB drifted (rare)
        if x.sum() != num_select:
            x = self._repair_cardinality(x, Q, num_select)

        selected_idx = np.where(x == 1)[0]
        selected_symbols = [symbols[i] for i in selected_idx]

        # 4. Equal-weight among selected (can be extended to mean-variance)
        weights = np.zeros(n, dtype=np.float64)
        weights[selected_idx] = 1.0 / num_select

        port_return = float(weights @ expected_returns)
        port_risk = float(np.sqrt(weights @ cov_matrix @ weights))
        sharpe = (port_return - RISK_FREE_RATE) / port_risk if port_risk > 0 else 0.0

        logger.info(
            "SB selected %s | return=%.6f risk=%.6f sharpe=%.4f",
            selected_symbols, port_return, port_risk, sharpe,
        )

        return {
            "selected_symbols": selected_symbols,
            "weights": weights.tolist(),
            "expected_return": port_return,
            "risk": port_risk,
            "sharpe_ratio": float(sharpe),
        }

    # ------------------------------------------------------------------
    # QUBO construction
    # ------------------------------------------------------------------
    def _build_qubo(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        num_select: int,
        risk_aversion: float,
    ) -> np.ndarray:
        """Build QUBO matrix for portfolio optimisation.

        Objective (to *minimise*):
            H = -Σ r_i x_i + λ Σ_{i≠j} cov_ij x_i x_j + μ (Σ x_i - K)²

        In QUBO form  xᵀ Q x  (x ∈ {0,1}ⁿ):

        Q[i,i] = -r_i + μ - 2 μ K      (diagonal / linear terms)
        Q[i,j] = λ cov_ij + μ          (off-diagonal / quadratic)

        The penalty term  μ (Σx_i − K)²  expands to
        μ Σx_i  − 2 μ K Σx_i  + μ K²  (constant dropped).
        Combined linear:  -r_i + μ - 2 μ K.
        """
        n = len(expected_returns)
        Q = np.zeros((n, n), dtype=np.float64)

        # Risk term (off-diagonal) — only i≠j contribute since x_i² = x_i for binary
        risk_term = risk_aversion * cov_matrix.copy()
        np.fill_diagonal(risk_term, 0.0)  # off-diagonal only

        # Penalty term for cardinality constraint  Σ x_i = K
        mu = self.penalty
        K = num_select

        # Diagonal: -return + penalty_unit - 2*penalty*K
        diag = -expected_returns + mu - 2.0 * mu * K
        # Off-diagonal: risk_aversion * cov + penalty
        off_diag = risk_term + mu

        Q = off_diag.copy()
        np.fill_diagonal(Q, diag)

        # Scale Q so that max |element| ≈ 1 (helps SB convergence)
        scale = np.max(np.abs(Q))
        if scale > 0:
            Q = Q / scale

        return Q

    # ------------------------------------------------------------------
    # Discrete Simulated Bifurcation core
    # ------------------------------------------------------------------
    def _run_sb(
        self,
        Q: np.ndarray,
        steps: int | None = None,
        dt: float | None = None,
    ) -> np.ndarray:
        """Run the discrete SB algorithm (dSB).

        Implements symplectic Euler integration of the Hamiltonian:

            H = (p²/2 + α/2 q² - 1) / 2   ... wait, the actual Hamiltonian:

            H = Σ_i [ p_i²/2 + (α-1) q_i²/2 ] + Σ_ij J_ij q_i q_j

        where α ramps from 0 to 1 (adiabatic pumping), J encodes the QUBO,
        and spins are sampled from sign(q_i).

        Integration (symplectic Euler, dSB variant):

            1.  p ← p + dt·(α−1)·q                         (momentum drift)
            2.  p ← p + dt·c₀·J·sign(q)                    (quadratic kick)
            3.  q ← q + dt·p                               (position drift)
            4.  inelastic walls:  if |q|>1 → q=±1, p=0     (boundary)
            5.  α = min(dt·step·p_slope, 1)                (pump update)
        """
        steps = steps or self.steps
        dt = dt or self.dt
        n = Q.shape[0]

        # Scale parameter (following the reference implementation)
        c0 = 0.5 * (n - 1) ** 0.5 / np.sqrt(np.sum(Q**2))

        # Multi-agent: shape (n, agents) – each agent is an independent oscillator set
        pos = 2.0 * self.rng.random((n, self.agents)) - 1.0  # position in [-1, 1]
        mom = 2.0 * self.rng.random((n, self.agents)) - 1.0  # momentum in [-1, 1]

        best_energy = np.inf
        best_spins = None

        for step in range(steps):
            alpha = min(dt * step * self.pressure_slope, 1.0)

            # 1. Momentum drift:  p += dt * (α - 1) * q
            mom += dt * (alpha - 1.0) * pos

            # 2. Quadratic kick:  p += dt * c0 * J * sign(q)
            sign_q = np.sign(pos)
            mom += dt * c0 * (Q @ sign_q)

            # 3. Position drift:  q += dt * p
            pos += dt * mom

            # 4. Inelastic walls
            outside = np.abs(pos) > 1.0
            pos = np.clip(pos, -1.0, 1.0)
            mom[outside] = 0.0

            # 5. Periodically check for convergence / record best
            if step % 500 == 0 or step == steps - 1:
                spins = np.where(pos >= 0, 1, -1).astype(np.float64)
                # QUBO is in 0/1 domain; convert Ising spins to binary
                binary = (spins + 1.0) / 2.0  # +1→1, -1→0
                # Energy: xᵀ Q x for each agent column
                energies = np.array([binary[:, a] @ Q @ binary[:, a] for a in range(self.agents)])
                min_agent = np.argmin(energies)
                if energies[min_agent] < best_energy:
                    best_energy = float(energies[min_agent])
                    best_spins = binary[:, min_agent].copy()

        return best_spins.astype(int)

    # ------------------------------------------------------------------
    # Repair / utilities
    # ------------------------------------------------------------------
    def _repair_cardinality(
        self, x: np.ndarray, Q: np.ndarray, num_select: int
    ) -> np.ndarray:
        """Greedy repair to enforce exact cardinality K.

        If too many assets are selected, drop those with worst marginal
        contribution; if too few, add those with best marginal contribution.
        """
        x = x.copy()
        n = len(x)
        current = int(x.sum())

        if current > num_select:
            # Remove assets with highest diagonal cost (worst individual)
            selected = np.where(x == 1)[0]
            # Marginal cost of keeping asset i = Q[i,i] + Σ_{j selected, j≠i} Q[i,j]
            margins = []
            for i in selected:
                others = x.copy()
                others[i] = 0
                margins.append(float(x @ Q @ x - others @ Q @ others))
            # Sort by descending marginal cost (remove highest cost first)
            order = np.argsort(margins)[::-1]
            for idx in order[: current - num_select]:
                x[selected[idx]] = 0

        elif current < num_select:
            # Add assets with lowest marginal cost
            unselected = np.where(x == 0)[0]
            margins = []
            for i in unselected:
                with_i = x.copy()
                with_i[i] = 1
                margins.append(float(with_i @ Q @ with_i - x @ Q @ x))
            order = np.argsort(margins)  # ascending = best to add
            for idx in order[: num_select - current]:
                x[unselected[idx]] = 1

        return x

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------
    def backtest(
        self,
        symbols: List[str],
        lookback_days: int = 252,
    ) -> dict:
        """Backtest SB-optimised portfolio vs equal-weight and random baselines.

        Fetches historical daily returns via yfinance, runs the SB optimizer
        on the first 80 % of the lookback window, then evaluates the
        out-of-sample performance of the selected portfolio vs benchmarks.

        Parameters
        ----------
        symbols : list of str
            Tickers to consider (N ≥ 10 recommended).
        lookback_days : int
            Total calendar days of history to fetch (default 252 trading days
            ≈ 1 year; yfinance uses calendar so we fetch extra).

        Returns
        -------
        dict with keys:
            ``sb_return``, ``equal_weight_return``, ``random_return``,
            ``sb_sharpe``, ``equal_sharpe``, ``selected_symbols``
        """
        import yfinance as yf

        # Fetch ~lookback_days * 1.4 calendar days to get enough trading days
        cal_days = int(lookback_days * 1.5)
        data = yf.download(
            " ".join(symbols),
            period=f"{cal_days}d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by="column",
        )

        if data.empty:
            raise ValueError("No data downloaded – check symbols / network")

        # Extract close prices
        if len(symbols) == 1:
            close = data["Close"].to_frame(name=symbols[0])
        else:
            close = data["Close"]

        close = close.dropna(how="all").dropna(axis=1, how="any")
        available = list(close.columns)
        if len(available) < 4:
            raise ValueError(f"Too few symbols with data: {available}")

        returns = close.pct_change().dropna()
        n_days = len(returns)

        # Split: 80 % in-sample, 20 % out-of-sample
        split = int(n_days * 0.8)
        in_sample = returns.iloc[:split]
        out_sample = returns.iloc[split:]

        mu = in_sample.mean().values  # daily expected returns
        cov = in_sample.cov().values
        K = min(5, len(available) // 2)

        # --- SB optimised portfolio ---
        sb_result = self.optimize_portfolio(
            available, mu, cov, num_select=K, risk_aversion=1.0
        )
        sb_selected = sb_result["selected_symbols"]
        sb_weights = np.array(sb_result["weights"])
        # Restrict weights to selected, normalise
        w = sb_weights[sb_weights > 0]
        w = w / w.sum()

        sb_daily = (out_sample[sb_selected] * w).sum(axis=1)
        sb_return = float(sb_daily.mean() * 252)  # annualised
        sb_vol = float(sb_daily.std() * np.sqrt(252))
        sb_sharpe = (sb_daily.mean() * 252 - 0.04) / sb_vol if sb_vol > 0 else 0.0

        # --- Equal-weight baseline ---
        eq_weights = np.ones(len(available)) / len(available)
        eq_daily = (out_sample[available] * eq_weights).sum(axis=1)
        eq_return = float(eq_daily.mean() * 252)
        eq_vol = float(eq_daily.std() * np.sqrt(252))
        eq_sharpe = (eq_daily.mean() * 252 - 0.04) / eq_vol if eq_vol > 0 else 0.0

        # --- Random selection baseline ---
        rng = np.random.default_rng(self.seed)
        random_idx = rng.choice(len(available), size=K, replace=False)
        random_selected = [available[i] for i in random_idx]
        rw = np.ones(K) / K
        rand_daily = (out_sample[random_selected] * rw).sum(axis=1)
        rand_return = float(rand_daily.mean() * 252)
        rand_vol = float(rand_daily.std() * np.sqrt(252))
        rand_sharpe = (rand_daily.mean() * 252 - 0.04) / rand_vol if rand_vol > 0 else 0.0

        result = {
            "selected_symbols": sb_selected,
            "sb_return": sb_return,
            "equal_weight_return": eq_return,
            "random_return": rand_return,
            "sb_sharpe": float(sb_sharpe),
            "equal_sharpe": float(eq_sharpe),
            "random_sharpe": float(rand_sharpe),
            "in_sample_days": split,
            "out_sample_days": n_days - split,
        }

        logger.info(
            "SB backtest | SB: ret=%.4f sharpe=%.4f | EQ: ret=%.4f sharpe=%.4f | "
            "RAND: ret=%.4f sharpe=%.4f",
            sb_return, sb_sharpe, eq_return, eq_sharpe, rand_return, rand_sharpe,
        )

        return result


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Synthetic test: 10 assets, select 5
    n = 10
    rng = np.random.default_rng(123)
    mu = rng.normal(0.001, 0.0005, n)
    # Random covariance with some structure
    L = rng.standard_normal((n, n))
    cov = L @ L.T / n
    np.fill_diagonal(cov, np.abs(np.diag(cov)) + 0.001)

    symbols = [f"TEST{i}" for i in range(n)]

    opt = SimulatedBifurcationOptimizer(steps=5000, agents=32, seed=42)
    result = opt.optimize_portfolio(symbols, mu, cov, num_select=5, risk_aversion=2.0)

    print("\n=== SB Optimizer Synthetic Test ===")
    print(f"Selected: {result['selected_symbols']}")
    print(f"Expected return: {result['expected_return']:.6f}")
    print(f"Risk (std):     {result['risk']:.6f}")
    print(f"Sharpe ratio:   {result['sharpe_ratio']:.4f}")
    print(f"Weights:        {result['weights']}")

    assert len(result["selected_symbols"]) == 5, "Should select exactly 5"
    assert all(w >= 0 for w in result["weights"]), "Weights should be non-negative"
    assert abs(sum(result["weights"]) - 1.0) < 1e-9, "Weights should sum to 1"
    print("\n✅ All assertions passed")