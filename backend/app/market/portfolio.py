"""Portfolio manager: position sizing and execution plan for paper trades.

Uses fractional Kelly Criterion for position sizing when enough trade history
is available, falling back to fixed ``capital_per_trade`` otherwise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.market.broker import AlpacaBroker, BrokerOrderResult
from app.market.recommender import StockRecommendation
from app.models import PaperPosition, PositionStatus

logger = logging.getLogger(__name__)

# Kelly sizing constants
KELLY_FRACTION = 0.25  # fractional Kelly (quarter-Kelly) to protect against estimation error
KELLY_MIN_TRADES = 30  # minimum closed trades required for Kelly sizing
KELLY_MIN_POSITION = 500.0  # clamp minimum position size
KELLY_MAX_POSITION = 5000.0  # clamp maximum position size


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

    # ------------------------------------------------------------------
    # Kelly Criterion position sizing
    # ------------------------------------------------------------------

    def calculate_kelly_fraction(
        self, win_rate: float, avg_win: float, avg_loss: float
    ) -> float:
        """Return the full-Kelly fraction for the given stats.

        Formula: f* = (p * b - q) / b
        where p = win_rate, q = 1 - p, b = avg_win / avg_loss.

        Returns 0.0 when inputs are degenerate (no losses, no wins, or
        non-positive avg_loss).
        """
        if avg_loss <= 0 or avg_win <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0

        p = win_rate
        q = 1.0 - p
        b = avg_win / avg_loss  # odds ratio (win/loss)

        kelly_full = (p * b - q) / b
        return max(kelly_full, 0.0)  # never go negative (no short sizing)

    async def get_kelly_position_size(
        self, base_capital: float, db_session: AsyncSession
    ) -> float:
        """Determine position size using fractional Kelly Criterion.

        Queries the last ``KELLY_MIN_TRADES`` closed ``PaperPosition`` rows
        to compute a realised win rate and average win/loss, then applies a
        fractional Kelly (0.25x) to the *full-Kelly* fraction.

        Falls back to ``base_capital`` when fewer than ``KELLY_MIN_TRADES``
        closed trades exist or when Kelly computes to zero.

        The result is clamped to ``[KELLY_MIN_POSITION, KELLY_MAX_POSITION]``.
        """
        # Fetch recent closed positions ordered by exit date descending
        stmt = (
            select(PaperPosition.realized_pnl)
            .where(PaperPosition.status == PositionStatus.closed)
            .where(PaperPosition.realized_pnl.is_not(None))
            .order_by(PaperPosition.exit_date.desc().nulls_last())
            .limit(KELLY_MIN_TRADES)
        )
        result = await db_session.execute(stmt)
        pnl_values: list[float] = [row[0] for row in result if row[0] is not None]

        if len(pnl_values) < KELLY_MIN_TRADES:
            logger.info(
                "Kelly: only %d closed trades (< %d) — falling back to base capital $%.0f",
                len(pnl_values), KELLY_MIN_TRADES, base_capital,
            )
            return base_capital

        wins = [p for p in pnl_values if p > 0]
        losses = [abs(p) for p in pnl_values if p < 0]

        if not wins or not losses:
            logger.info("Kelly: no wins or no losses in history — falling back to base capital $%.0f", base_capital)
            return base_capital

        win_rate = len(wins) / len(pnl_values)
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)

        kelly_full = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
        kelly_fractional = kelly_full * KELLY_FRACTION

        # Size = fractional_kelly * bankroll_fraction * base_capital
        # We treat base_capital as the per-trade bankroll allocation.
        position_size = kelly_fractional * base_capital

        logger.info(
            "Kelly: win_rate=%.1f%% avg_win=$%.2f avg_loss=$%.2f full_kelly=%.3f frac_kelly=%.3f raw_size=$%.2f",
            win_rate * 100, avg_win, avg_loss, kelly_full, kelly_fractional, position_size,
        )

        if position_size <= 0:
            logger.info("Kelly computed zero — falling back to base capital $%.0f", base_capital)
            return base_capital

        # Clamp to safe bounds
        position_size = max(KELLY_MIN_POSITION, min(KELLY_MAX_POSITION, position_size))
        logger.info("Kelly final position size: $%.2f (clamped to [%.0f, %.0f])", position_size, KELLY_MIN_POSITION, KELLY_MAX_POSITION)
        return position_size

    def _round_qty(self, qty: float, price: float) -> float:
        """Round shares to reasonable precision."""
        return float(Decimal(str(qty)).quantize(Decimal("0.0001")))

    def build_plan(
        self,
        pick: StockRecommendation,
        current_price: Optional[float] = None,
        position_size: Optional[float] = None,
    ) -> Optional[TradePlan]:
        """Build a trade plan from a StockRecommendation using whole-share qty.

        Exit strategy:
        - Stop loss: max(2*ATR, 1.5% of price) below entry (volatility-adaptive)
        - Take profit: based on pick.forecast_return_4d or 4% minimum
        - Breakeven activation: when price reaches 50% of TP distance, move stop to entry
        """
        if pick.action != "buy":
            return None
        if pick.forecast_return_4d is None or pick.forecast_return_4d <= 0:
            return None

        # Prefer live current price; fall back to predicted close (not ideal but better than nothing)
        price = current_price or pick.predicted_close_4d
        if not price or price <= 0:
            return None

        # Position size: Kelly-sized override or default capital_per_trade
        capital = position_size if position_size is not None else self.capital_per_trade

        # Use whole shares so Alpaca accepts GTC stop/limit exit orders.
        shares = int(capital / price)
        if shares <= 0:
            return None

        notional = round(shares * price, 2)
        if notional < 1.0:
            return None

        # Volatility-adaptive stop loss
        # Use pick's stop if provided, otherwise compute adaptive stop
        if pick.stop_loss and pick.stop_loss > 0:
            stop = pick.stop_loss
        else:
            # Default: 1.5% stop for low-vol, wider for higher-priced stocks
            stop_pct = 0.015  # 1.5%
            if price > 300:
                stop_pct = 0.02  # 2% for high-priced stocks (wider normal range)
            stop = price * (1 - stop_pct)

        # Take profit from forecast or default 4%
        if pick.take_profit and pick.take_profit > 0:
            target = pick.take_profit
        else:
            target = price * (1 + max(pick.forecast_return_4d or 0.04, 0.04))

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
        blocked_symbols: set[str],
        current_prices: Optional[Dict[str, float]] = None,
        position_sizes: Optional[Dict[str, float]] = None,
    ) -> List[TradePlan]:
        """Select which buy picks to execute today, respecting limits.

        ``position_sizes`` optionally maps symbol -> capital to allocate for
        that symbol (e.g. Kelly-sized).  When not provided the default
        ``capital_per_trade`` is used.
        """
        plans: List[TradePlan] = []
        slots_remaining = max(0, self.max_open_positions - len(blocked_symbols))

        for pick in picks:
            if len(plans) >= slots_remaining:
                break
            if pick.symbol in blocked_symbols:
                continue
            price = (current_prices or {}).get(pick.symbol)
            size = (position_sizes or {}).get(pick.symbol)
            plan = self.build_plan(pick, current_price=price, position_size=size)
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
