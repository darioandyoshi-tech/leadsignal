"""Portfolio manager: position sizing and execution plan for paper trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from app.config import get_settings
from app.market.broker import AlpacaBroker, BrokerOrderResult
from app.market.recommender import StockRecommendation


@dataclass
class TradePlan:
    symbol: str
    action: str  # buy / skip
    shares: float
    notional: float
    entry_price: float
    stop_loss: float
    take_profit: float
    max_hold_days: int
    reason: str


class PaperPortfolioManager:
    """Decides which picks to execute and how much to buy."""

    def __init__(
        self,
        capital_per_trade: Optional[float] = None,
        max_open_positions: Optional[int] = None,
        max_hold_days: Optional[int] = None,
        broker: Optional[AlpacaBroker] = None,
    ):
        settings = get_settings()
        self.capital_per_trade = capital_per_trade if capital_per_trade is not None else settings.alpaca_capital_per_trade
        self.max_open_positions = max_open_positions if max_open_positions is not None else settings.alpaca_max_open_positions
        self.max_hold_days = max_hold_days if max_hold_days is not None else settings.alpaca_max_hold_days
        self.broker = broker

    def _round_qty(self, qty: float, price: float) -> float:
        """Round shares to reasonable precision."""
        return float(Decimal(str(qty)).quantize(Decimal("0.0001")))

    def build_plan(self, pick: StockRecommendation, current_price: Optional[float] = None) -> Optional[TradePlan]:
        """Build a trade plan from a StockRecommendation using whole-share qty."""
        if pick.action != "buy":
            return None
        if pick.forecast_return_4d is None or pick.forecast_return_4d <= 0:
            return None

        price = current_price or pick.predicted_close_4d
        if not price or price <= 0:
            return None

        # Use whole shares so Alpaca accepts GTC stop/limit exit orders.
        shares = int(self.capital_per_trade / price)
        if shares <= 0:
            return None

        notional = round(shares * price, 2)
        if notional < 1.0:
            return None

        stop = pick.stop_loss or price * 0.96
        target = pick.take_profit or price * 1.04

        return TradePlan(
            symbol=pick.symbol,
            action="buy",
            shares=shares,
            notional=notional,
            entry_price=price,
            stop_loss=round(stop, 2),
            take_profit=round(target, 2),
            max_hold_days=self.max_hold_days,
            reason=pick.reasoning,
        )

    def select_picks_to_buy(
        self,
        picks: List[StockRecommendation],
        current_open_positions: List[Dict],
    ) -> List[TradePlan]:
        """Select which buy picks to execute today, respecting limits."""
        open_symbols = {p["symbol"] for p in current_open_positions}
        plans: List[TradePlan] = []
        slots_remaining = max(0, self.max_open_positions - len(current_open_positions))

        for pick in picks:
            if len(plans) >= slots_remaining:
                break
            if pick.symbol in open_symbols:
                continue
            plan = self.build_plan(pick)
            if plan:
                plans.append(plan)

        return plans

    def execute_buy(
        self, plan: TradePlan
    ) -> Dict:
        """Submit a bracket order with whole-share qty so exit legs are attached and GTC."""
        if not self.broker:
            return {"success": False, "error": "No broker configured"}

        result = self.broker.submit_bracket_entry(
            symbol=plan.symbol,
            qty=plan.shares,
            take_profit_price=plan.take_profit,
            stop_loss_price=plan.stop_loss,
        )
        if not result.success:
            return {
                "success": False,
                "stage": "bracket_entry",
                "error": result.error,
                "order": result.raw,
            }

        return {
            "success": True,
            "symbol": plan.symbol,
            "shares": plan.shares,
            "notional": plan.notional,
            "entry_price": plan.entry_price,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "order": {
                "broker_order_id": result.broker_order_id,
                "status": result.status,
                "filled_qty": result.filled_qty,
                "filled_avg_price": result.filled_avg_price,
                "raw": result.raw,
            },
        }
