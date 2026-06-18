"""Short-term stock scoring for 1-4 day holds."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
import numpy as np
import pandas as pd

from app.config import get_settings


@dataclass
class StockScore:
    symbol: str
    score: float
    forecast_return_4d: Optional[float]
    predicted_close_4d: Optional[float]
    latest_close: float
    rsi_14: Optional[float]
    macd: Optional[float]
    volatility_20d: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    features: Dict[str, float]
    error: Optional[str] = None


class StockScorer:
    def __init__(self, timesfm_url: Optional[str] = None, api_key: Optional[str] = None):
        settings = get_settings()
        self.timesfm_url = timesfm_url or settings.timesfm_url or os.environ.get("TIMESFM_URL", "")
        self.api_key = api_key or settings.timesfm_api_key or os.environ.get("TIMESFM_API_KEY", "")

    def score_all(self, features_df: pd.DataFrame) -> List[StockScore]:
        """Score every symbol based on latest technicals + forecast."""
        results: List[StockScore] = []
        for symbol, group in features_df.groupby("symbol"):
            latest = group.sort_values("date").iloc[-1]
            score, forecast_return, predicted_close, error = self._compute_score(symbol, group)

            close = float(latest["close"])
            atr = latest.get("atr_14")
            stop = close - 2 * float(atr) if pd.notna(atr) else close * 0.95
            target = close + 4 * float(atr) if pd.notna(atr) else close * 1.05

            results.append(
                StockScore(
                    symbol=symbol,
                    score=round(score, 4),
                    forecast_return_4d=forecast_return,
                    predicted_close_4d=predicted_close,
                    latest_close=close,
                    rsi_14=float(latest["rsi_14"]) if pd.notna(latest["rsi_14"]) else None,
                    macd=float(latest["macd"]) if pd.notna(latest["macd"]) else None,
                    volatility_20d=float(latest["volatility_20d"]) if pd.notna(latest["volatility_20d"]) else None,
                    stop_loss=round(stop, 4),
                    take_profit=round(target, 4),
                    features={
                        "bb_position": float(latest["bb_position"]) if pd.notna(latest["bb_position"]) else None,
                        "volume_ratio": float(latest["volume_ratio"]) if pd.notna(latest["volume_ratio"]) else None,
                        "return_4d": float(latest["return_4d"]) if pd.notna(latest["return_4d"]) else None,
                    },
                    error=error,
                )
            )
        return results

    def _compute_score(self, symbol: str, group: pd.DataFrame) -> tuple[float, Optional[float], Optional[float], Optional[str]]:
        latest = group.sort_values("date").iloc[-1]
        closes = group.sort_values("date")["close"].dropna().tolist()
        if len(closes) < 30:
            return 0.0, None, None, "insufficient history"

        # Try TimesFM forecast
        forecast_return, predicted_close, error = self._timesfm_forecast(symbol, closes)

        # Technical components
        rsi = latest["rsi_14"] if pd.notna(latest["rsi_14"]) else 50
        macd = latest["macd"] if pd.notna(latest["macd"]) else 0
        bb_pos = latest["bb_position"] if pd.notna(latest["bb_position"]) else 0.5
        vol_ratio = latest["volume_ratio"] if pd.notna(latest["volume_ratio"]) else 1.0
        vol = latest["volatility_20d"] if pd.notna(latest["volatility_20d"]) else 0.5

        # Momentum score: prefer slight oversold bounce with positive MACD
        rsi_score = 1.0 - abs(rsi - 55) / 45.0  # best around 55
        macd_score = 0.5 + 0.5 * np.sign(macd) if pd.notna(macd) else 0.5
        bb_score = 1.0 - abs(bb_pos - 0.35) / 0.65  # best near lower band
        volume_score = min(1.0, vol_ratio / 2.0)

        # Volatility penalty: too volatile is risky for short holds
        vol_score = max(0.0, 1.0 - vol * 2.0)

        # Forecast score with directional penalty for negative forecasts
        forecast_score = 0.5
        if forecast_return is not None:
            if forecast_return < 0:
                # Penalize negative forecasts more aggressively
                forecast_score = max(0.0, 0.5 + 2.0 * forecast_return)
            else:
                # Map 0..+5% to 0.5..1.0
                forecast_score = 0.5 + 0.5 * min(1.0, forecast_return / 0.05)

        weights = {"rsi": 0.15, "macd": 0.15, "bb": 0.10, "volume": 0.10, "vol": 0.10, "forecast": 0.40}
        score = (
            rsi_score * weights["rsi"]
            + macd_score * weights["macd"]
            + bb_score * weights["bb"]
            + volume_score * weights["volume"]
            + vol_score * weights["vol"]
            + forecast_score * weights["forecast"]
        )
        return score, forecast_return, predicted_close, error

    def _timesfm_forecast(self, symbol: str, closes: List[float]) -> tuple[Optional[float], Optional[float], Optional[str]]:
        if not self.timesfm_url:
            return None, None, "TimesFM URL not configured"
        try:
            resp = httpx.post(
                f"{self.timesfm_url}/forecast",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                json={
                    "series": closes,
                    "horizon": 4,
                    "return_quantiles": True,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            point = data.get("point", [])
            if not point:
                return None, None, "empty forecast"
            predicted = float(point[-1])
            current = float(closes[-1])
            return (predicted - current) / current, predicted, None
        except Exception as exc:
            return None, None, f"TimesFM error: {exc}"
