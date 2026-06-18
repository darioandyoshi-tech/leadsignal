"""Recommender for 1-4 day stock holds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .scorer import StockScore


@dataclass
class StockRecommendation:
    symbol: str
    action: str  # buy, hold, avoid
    confidence: float
    score: float
    forecast_return_4d: Optional[float]
    predicted_close_4d: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    max_hold_days: int
    reasoning: str
    playbook: Optional[str]


class StockRecommender:
    def __init__(self, buy_threshold: float = 0.62, avoid_threshold: float = 0.40, max_hold_days: int = 4):
        self.buy_threshold = buy_threshold
        self.avoid_threshold = avoid_threshold
        self.max_hold_days = max_hold_days

    def recommend(self, score: StockScore) -> StockRecommendation:
        action = "avoid"
        reasons = []
        playbook = None

        if score.score >= self.buy_threshold:
            # Do not recommend buy if forecast is negative
            if score.forecast_return_4d is not None and score.forecast_return_4d < 0:
                return StockRecommendation(
                    symbol=score.symbol,
                    action="avoid",
                    confidence=1.0 - score.score,
                    score=score.score,
                    forecast_return_4d=score.forecast_return_4d,
                    predicted_close_4d=score.predicted_close_4d,
                    stop_loss=score.stop_loss,
                    take_profit=score.take_profit,
                    max_hold_days=self.max_hold_days,
                    reasoning="Technical setup looks good but 4-day forecast is negative; skip entry",
                    playbook="Wait for forecast to turn positive before buying.",
                )
            action = "buy"
            reasons.append(f"Short-term score {score.score:.2f} above buy threshold")
            if score.forecast_return_4d is not None and score.forecast_return_4d > 0:
                reasons.append(f"4-day forecast return +{score.forecast_return_4d*100:.1f}%")
            if score.rsi_14 is not None and 40 <= score.rsi_14 <= 65:
                reasons.append("RSI in favorable momentum zone")
            if score.features.get("volume_ratio", 1.0) > 1.2:
                reasons.append("Above-average volume confirming interest")
            playbook = f"Buy at ${score.latest_close:.2f}; target ${score.take_profit:.2f}; stop ${score.stop_loss:.2f}; hold up to {self.max_hold_days} days."
        elif score.score >= self.avoid_threshold:
            action = "hold"
            reasons.append(f"Score {score.score:.2f} is neutral; wait for better setup")
            playbook = "Monitor for a breakout or pullback entry."
        else:
            reasons.append(f"Score {score.score:.2f} too low")
            playbook = "Avoid new entry."

        return StockRecommendation(
            symbol=score.symbol,
            action=action,
            confidence=min(1.0, score.score + 0.15),
            score=score.score,
            forecast_return_4d=score.forecast_return_4d,
            predicted_close_4d=score.predicted_close_4d,
            stop_loss=score.stop_loss,
            take_profit=score.take_profit,
            max_hold_days=self.max_hold_days,
            reasoning="; ".join(reasons),
            playbook=playbook,
        )

    def rank(self, scores: List[StockScore], top_n: int = 10) -> List[StockRecommendation]:
        ranked = sorted(scores, key=lambda s: s.score, reverse=True)
        return [self.recommend(s) for s in ranked[:top_n]]
