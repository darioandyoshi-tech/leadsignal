"""Alpaca paper broker client for LeadSignal market picks."""

from __future__ import annotations

import enum
import json
import os
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetAssetsRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass, QueryOrderStatus
from alpaca.common.exceptions import APIError

from app.config import get_settings


@dataclass
class BrokerOrderResult:
    success: bool
    broker_order_id: Optional[str]
    status: str
    filled_qty: Optional[float]
    filled_avg_price: Optional[float]
    raw: Dict
    error: Optional[str] = None


class AlpacaBroker:
    """Thin wrapper around alpaca-py trading client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: Optional[bool] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.alpaca_api_key or os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = secret_key or settings.alpaca_secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
        self.paper = paper if paper is not None else settings.alpaca_paper
        if not self.api_key or not self.secret_key:
            raise RuntimeError("Alpaca API key and secret are required")
        self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)

    def _normalize_status(self, status: str) -> str:
        """Map Alpaca order status to our simplified enum strings."""
        s = str(status).upper().replace("ORDERSTATUS.", "")
        mapping = {
            "NEW": "pending",
            "PENDING_NEW": "pending",
            "ACCEPTED": "accepted",
            "PARTIALLY_FILLED": "partially_filled",
            "FILLED": "filled",
            "REJECTED": "rejected",
            "CANCELED": "cancelled",
            "CANCELLED": "cancelled",
            "EXPIRED": "expired",
            "DONE_FOR_DAY": "filled",
            "REPLACED": "accepted",
        }
        return mapping.get(s, s.lower())

    @staticmethod
    def _json_safe(raw: Dict) -> Dict:
        """Convert UUID/enum/datetime objects in Alpaca raw dict to JSON-safe values."""
        import json

        def serialize(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, enum.Enum):
                return obj.value
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return obj

        try:
            return json.loads(json.dumps(raw, default=serialize))
        except Exception:
            return {"serialization_error": str(raw)[:500]}

    def get_account(self) -> Dict:
        """Return Alpaca account summary."""
        try:
            account = self.client.get_account()
            return {
                "id": account.id,
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "status": account.status,
                "currency": account.currency,
            }
        except APIError as exc:
            return {"error": str(exc), "code": exc.code}

    def get_positions(self) -> List[Dict]:
        """Return current open positions at Alpaca."""
        try:
            positions = self.client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "avg_entry_price": float(p.avg_entry_price),
                    "unrealized_plpc": float(p.unrealized_plpc),
                    "current_price": float(p.current_price),
                }
                for p in positions
            ]
        except APIError as exc:
            return [{"error": str(exc), "code": exc.code}]

    def is_tradable(self, symbol: str) -> bool:
        """Check if symbol is tradable on Alpaca."""
        try:
            req = GetAssetsRequest(symbol=symbol)
            assets = self.client.get_all_assets(req)
            if not assets:
                return False
            return assets[0].tradable and assets[0].status == "active"
        except APIError:
            return False

    def submit_market_buy(
        self, symbol: str, notional: Optional[float] = None, qty: Optional[float] = None
    ) -> BrokerOrderResult:
        """Submit a market buy order by notional or qty."""
        try:
            if notional:
                req = MarketOrderRequest(
                    symbol=symbol,
                    notional=round(float(notional), 2),
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            elif qty:
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=round(float(qty), 8),
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                return BrokerOrderResult(
                    success=False,
                    broker_order_id=None,
                    status="rejected",
                    filled_qty=None,
                    filled_avg_price=None,
                    raw={},
                    error="Either notional or qty must be provided",
                )
            order = self.client.submit_order(req)
            return BrokerOrderResult(
                success=True,
                broker_order_id=order.id,
                status=self._normalize_status(order.status),
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                raw=self._json_safe(order.model_dump() if hasattr(order, "model_dump") else {}),
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def submit_stop_limit_sell(
        self,
        symbol: str,
        qty: float,
        stop_price: float,
        limit_price: float,
    ) -> BrokerOrderResult:
        """Submit a GTC stop-limit sell order."""
        try:
            req = StopLimitOrderRequest(
                symbol=symbol,
                qty=round(float(qty), 8),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                stop_price=round(float(stop_price), 2),
                limit_price=round(float(limit_price), 2),
            )
            order = self.client.submit_order(req)
            return BrokerOrderResult(
                success=True,
                broker_order_id=order.id,
                status=self._normalize_status(order.status),
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                raw=self._json_safe(order.model_dump() if hasattr(order, "model_dump") else {}),
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def submit_limit_sell(
        self,
        symbol: str,
        qty: float,
        limit_price: float,
    ) -> BrokerOrderResult:
        """Submit a GTC limit sell order (take profit)."""
        try:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=round(float(qty), 8),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=round(float(limit_price), 2),
            )
            order = self.client.submit_order(req)
            return BrokerOrderResult(
                success=True,
                broker_order_id=order.id,
                status=self._normalize_status(order.status),
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                raw=self._json_safe(order.model_dump() if hasattr(order, "model_dump") else {}),
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def submit_bracket_entry(
        self,
        symbol: str,
        qty: float,
        take_profit_price: float,
        stop_loss_price: float,
    ) -> BrokerOrderResult:
        """Submit a bracket market buy order with attached take-profit + stop-loss legs."""
        try:
            qty = round(float(qty), 8)
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit={"limit_price": round(float(take_profit_price), 2)},
                stop_loss={"stop_price": round(float(stop_loss_price), 2)},
            )
            order = self.client.submit_order(req)
            return BrokerOrderResult(
                success=True,
                broker_order_id=order.id,
                status=self._normalize_status(order.status),
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                raw=self._json_safe(order.model_dump() if hasattr(order, "model_dump") else {}),
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def submit_oco_exit(
        self,
        symbol: str,
        qty: float,
        take_profit_price: float,
        stop_loss_price: float,
    ) -> BrokerOrderResult:
        """Submit two GTC exit orders: limit take-profit and stop-limit stop-loss.

        alpaca-py does not expose a standalone OCOOrderRequest; we model the
        risk-management intent by placing both legs separately.  The stop leg
        is a stop-limit with limit slightly below the stop to protect fills.
        """
        try:
            qty = round(float(qty), 8)
            stop_leg = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                stop_price=round(float(stop_loss_price), 2),
                limit_price=round(float(stop_loss_price) * 0.99, 2),
            )
            tp_leg = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=round(float(take_profit_price), 2),
            )
            stop_order = self.client.submit_order(stop_leg)
            tp_order = self.client.submit_order(tp_leg)
            return BrokerOrderResult(
                success=True,
                broker_order_id=str(stop_order.id),
                status=str(stop_order.status),
                filled_qty=float(stop_order.filled_qty) if stop_order.filled_qty else None,
                filled_avg_price=float(stop_order.filled_avg_price) if stop_order.filled_avg_price else None,
                raw={
                    "stop_order": stop_order.model_dump() if hasattr(stop_order, "model_dump") else {},
                    "take_profit_order": tp_order.model_dump() if hasattr(tp_order, "model_dump") else {},
                },
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def submit_market_sell(
        self, symbol: str, qty: Optional[float] = None, notional: Optional[float] = None
    ) -> BrokerOrderResult:
        """Submit a market sell order by qty or notional."""
        try:
            kwargs = {"symbol": symbol, "side": OrderSide.SELL, "time_in_force": TimeInForce.DAY}
            if qty:
                kwargs["qty"] = round(float(qty), 8)
            elif notional:
                kwargs["notional"] = round(float(notional), 2)
            else:
                return BrokerOrderResult(
                    success=False,
                    broker_order_id=None,
                    status="rejected",
                    filled_qty=None,
                    filled_avg_price=None,
                    raw={},
                    error="Either notional or qty must be provided",
                )
            order = self.client.submit_order(MarketOrderRequest(**kwargs))
            return BrokerOrderResult(
                success=True,
                broker_order_id=order.id,
                status=self._normalize_status(order.status),
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                raw=self._json_safe(order.model_dump() if hasattr(order, "model_dump") else {}),
            )
        except APIError as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                status="rejected",
                filled_qty=None,
                filled_avg_price=None,
                raw={},
                error=str(exc),
            )

    def get_order(self, broker_order_id: str) -> Dict:
        """Fetch order details by Alpaca order id."""
        try:
            order = self.client.get_order_by_id(broker_order_id)
            return order.model_dump() if hasattr(order, "model_dump") else {"id": order.id}
        except APIError as exc:
            return {"error": str(exc), "code": exc.code}

    def cancel_all_orders(self) -> List[Dict]:
        """Cancel all open orders. Use with care."""
        try:
            return [o.model_dump() if hasattr(o, "model_dump") else {"id": o.id} for o in self.client.cancel_orders()]
        except APIError as exc:
            return [{"error": str(exc), "code": exc.code}]
