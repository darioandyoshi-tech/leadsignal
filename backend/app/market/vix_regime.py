"""VIX term-structure regime filter for LeadSignal.

The VIX term structure is one of the most reliable market-regime indicators:

- **Contango (normal):** VIX < VIX3M → calm market, normal position sizes,
  wider stops.
- **Backwardation (stress):** VIX > VIX3M → turbulent market, reduce
  position sizes, tighten stops.
- **Steep contango:** VIX much lower than VIX3M → very calm, but potential
  complacency risk.

This module fetches spot VIX (``^VIX``) and 3-month VIX (``^VIX3M``) via
*yfinance*.  If ``^VIX3M`` is unavailable it falls back to a 63-trading-day
moving average of spot VIX as a proxy.

Usage::

    from app.market.vix_regime import VIXRegimeFilter

    vrf = VIXRegimeFilter()
    regime = vrf.get_regime()
    print(regime["regime"], regime["position_multiplier"])

    if vrf.should_reduce_positions():
        ...  # scale down or skip new entries
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIX_SPOT_TICKER = "^VIX"
_VIX_3M_TICKER = "^VIX3M"
_VIX_3M_MA_WINDOW = 63          # ~3 trading months
_VIX_6M_TICKER = "^VIX6M"      # bonus, used for broader context

# Regime thresholds (spread_pct = (vix_3m - vix_spot) / vix_spot * 100)
_STEEP_CONTANGO_THRESHOLD = 20.0   # VIX3M > 20% above VIX spot
_BACKWARDATION_THRESHOLD = 0.0     # VIX3M <= VIX spot

# VIX absolute level thresholds for extreme-stress scaling
_VIX_EXTREME_LEVEL = 30.0          # VIX >= 30 → extreme stress
_VIX_STRESS_LEVEL = 22.0           # VIX >= 22 → moderate stress

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class VIXRegimeResult:
    """Structured result from :meth:`VIXRegimeFilter.get_regime`."""

    regime: str                   # "contango" | "backwardation" | "steep_contango"
    vix_spot: float
    vix_3m: float
    spread_pct: float             # (vix_3m - vix_spot) / vix_spot * 100
    position_multiplier: float     # 1.0 / 0.5 / 0.25
    stop_multiplier: float         # 1.0 / 0.7 / 0.5
    vix_6m: Optional[float] = None
    as_of: Optional[str] = None    # ISO date of last data
    source_3m: str = "index"       # "index" or "ma63_proxy"
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


class VIXRegimeFilter:
    """Fetch VIX / VIX3M and determine the current market regime.

    Parameters
    ----------
    lookback_days:
        How many days of history to fetch for ``^VIX`` (used for the MA
        fallback).  Default 200 (enough for a 63-day MA and context).
    """

    def __init__(self, lookback_days: int = 200) -> None:
        self.lookback_days = lookback_days

    # -- public API --------------------------------------------------------

    def get_regime(self) -> dict:
        """Return the current VIX regime as a plain dict.

        Keys: ``regime``, ``vix_spot``, ``vix_3m``, ``spread_pct``,
        ``position_multiplier``, ``stop_multiplier``, ``vix_6m``,
        ``as_of``, ``source_3m``, ``recommendation``.
        """
        result = self._compute_regime()
        return asdict(result)  # type: ignore[arg-type]

    def should_reduce_positions(self) -> bool:
        """Return *True* when position sizes should be reduced."""
        return self.get_regime()["position_multiplier"] < 1.0

    def get_position_multiplier(self) -> float:
        """Return the position-size multiplier for the current regime."""
        return float(self.get_regime()["position_multiplier"])

    def get_stop_multiplier(self) -> float:
        """Return the stop-loss multiplier for the current regime."""
        return float(self.get_regime()["stop_multiplier"])

    # -- internals --------------------------------------------------------

    def _fetch_vix_data(self) -> tuple[pd.Series, Optional[float], Optional[float], Optional[str]]:
        """Fetch spot VIX, VIX3M, VIX6M, and the as-of date.

        Returns
        -------
        (vix_close_series, vix_3m_value, vix_6m_value, as_of_str)
        """
        # Spot VIX
        vix_df = yf.download(_VIX_SPOT_TICKER, period=f"{self.lookback_days}d", progress=False)
        if vix_df.empty:
            raise RuntimeError("Failed to fetch ^VIX data from yfinance")

        # Handle MultiIndex columns (yfinance >= 0.2.x)
        close_col = vix_df["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        vix_close = close_col.dropna()
        if vix_close.empty:
            raise RuntimeError("VIX close series is empty after dropna")

        as_of = str(vix_close.index[-1].date())

        # Try to get ^VIX3M directly
        vix_3m_val: Optional[float] = None
        try:
            vix3m_df = yf.download(_VIX_3M_TICKER, period="5d", progress=False)
            if not vix3m_df.empty:
                c3m = vix3m_df["Close"].iloc[-1]
                if isinstance(c3m, pd.Series):
                    c3m = c3m.iloc[0]
                vix_3m_val = float(c3m)
        except Exception as exc:
            logger.warning("Could not fetch ^VIX3M: %s — will use MA proxy", exc)

        # Try VIX6M for broader context (optional)
        vix_6m_val: Optional[float] = None
        try:
            vix6m_df = yf.download(_VIX_6M_TICKER, period="5d", progress=False)
            if not vix6m_df.empty:
                c6m = vix6m_df["Close"].iloc[-1]
                if isinstance(c6m, pd.Series):
                    c6m = c6m.iloc[0]
                vix_6m_val = float(c6m)
        except Exception as exc:
            logger.debug("Could not fetch ^VIX6M: %s", exc)

        return vix_close, vix_3m_val, vix_6m_val, as_of

    def _compute_regime(self) -> VIXRegimeResult:
        vix_close, vix_3m_raw, vix_6m_val, as_of = self._fetch_vix_data()

        vix_spot = float(vix_close.iloc[-1])

        # Determine VIX3M value and source
        if vix_3m_raw is not None and not math.isnan(vix_3m_raw):
            vix_3m = vix_3m_raw
            source_3m = "index"
        else:
            # Fallback: 63-trading-day moving average
            if len(vix_close) >= _VIX_3M_MA_WINDOW:
                vix_3m = float(vix_close.rolling(_VIX_3M_MA_WINDOW).mean().iloc[-1])
            else:
                # Not enough history — use the spot as a safe fallback
                vix_3m = vix_spot
            source_3m = "ma63_proxy"

        spread_pct = ((vix_3m - vix_spot) / vix_spot) * 100.0

        # Classify regime
        if spread_pct >= _STEEP_CONTANGO_THRESHOLD:
            regime = "steep_contango"
        elif spread_pct > _BACKWARDATION_THRESHOLD:
            regime = "contango"
        else:
            regime = "backwardation"

        # Determine multipliers based on regime and absolute VIX level
        position_mult, stop_mult, rec = self._multipliers(regime, vix_spot, spread_pct)

        return VIXRegimeResult(
            regime=regime,
            vix_spot=round(vix_spot, 2),
            vix_3m=round(vix_3m, 2),
            spread_pct=round(spread_pct, 2),
            position_multiplier=position_mult,
            stop_multiplier=stop_mult,
            vix_6m=round(vix_6m_val, 2) if vix_6m_val is not None else None,
            as_of=as_of,
            source_3m=source_3m,
            recommendation=rec,
        )

    @staticmethod
    def _multipliers(
        regime: str, vix_spot: float, spread_pct: float
    ) -> tuple[float, float, str]:
        """Return (position_multiplier, stop_multiplier, recommendation)."""

        if regime == "backwardation":
            # Market stress
            if vix_spot >= _VIX_EXTREME_LEVEL:
                # Extreme stress — aggressive de-risk
                return (
                    0.25,
                    0.50,
                    "Extreme backwardation: VIX ≥ 30. Halve position sizes to 25% "
                    "and tighten stops to 50%. Consider only hedged or defensive "
                    "entries.",
                )
            elif vix_spot >= _VIX_STRESS_LEVEL:
                return (
                    0.50,
                    0.70,
                    "Backwardation with elevated VIX: reduce positions to 50% and "
                    "tighten stops to 70%. favour quality, avoid speculative names.",
                )
            else:
                return (
                    0.50,
                    0.70,
                    "Mild backwardation: VIX above VIX3M. Reduce position sizes "
                    "to 50%, tighten stops to 70%. Wait for term structure to "
                    "normalise before resuming full risk.",
                )

        if regime == "steep_contango":
            return (
                0.75,
                1.0,
                "Steep contango: VIX3M > 20% above spot. Market very calm but "
                "complacency risk is elevated. Slightly reduce sizes to 75%; "
                "keep normal stops. Stay alert for sudden regime shifts.",
            )

        # Normal contango
        return (
            1.0,
            1.0,
            "Contango: VIX below VIX3M, normal term structure. Full position "
            "sizes and standard stops.",
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def get_regime_snapshot() -> dict:
    """One-shot helper: return ``VIXRegimeFilter().get_regime()``."""
    return VIXRegimeFilter().get_regime()