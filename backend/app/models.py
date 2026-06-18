
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, Boolean, ForeignKey,
    JSON, Enum, UUID as SQLUUID, Index, ARRAY
)
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class Tier(str, enum.Enum):
    starter = "starter"
    pro = "pro"
    growth = "growth"
    enterprise = "enterprise"


class SignalType(str, enum.Enum):
    hiring_spike = "hiring_spike"
    negative_review_cluster = "negative_review_cluster"
    permit_filing = "permit_filing"
    parcel_change = "parcel_change"
    tax_delinquency = "tax_delinquency"
    gov_contract_award = "gov_contract_award"
    business_license = "business_license"
    ucc_filing = "ucc_filing"
    new_business_registration = "new_business_registration"
    land_bank_property = "land_bank_property"


class AlertChannel(str, enum.Enum):
    email = "email"
    slack = "slack"
    discord = "discord"
    webhook = "webhook"
    dashboard = "dashboard"


class TradeAction(str, enum.Enum):
    buy = "buy"
    hold = "hold"
    sell = "sell"
    avoid = "avoid"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    submitted = "submitted"
    accepted = "accepted"
    partially_filled = "partially_filled"
    filled = "filled"
    rejected = "rejected"
    cancelled = "cancelled"
    expired = "expired"


class PositionStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    liquidating = "liquidating"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"


class Company(Base):
    __tablename__ = "companies"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)
    website = Column(String(512), nullable=True)
    industry = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True, index=True)
    state = Column(String(64), nullable=True, index=True)
    zip_code = Column(String(32), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    external_ids = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    signals = relationship("Signal", back_populates="company")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(SQLUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    signal_type = Column(Enum(SignalType), nullable=False, index=True)
    severity = Column(Integer, default=1)
    headline = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)
    source_url = Column(String(1024), nullable=True)
    source_api = Column(String(128), nullable=True)
    location_name = Column(String(255), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    published_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    is_alerted = Column(Boolean, default=False, index=True)

    company = relationship("Company", back_populates="signals")

    __table_args__ = (
        Index("ix_signals_type_detected", "signal_type", "detected_at"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(SQLUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(Enum(Tier), nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.incomplete)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(SQLUUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    signal_ids = Column(JSON, default=list)
    channel = Column(Enum(AlertChannel), nullable=False)
    status = Column(String(64), default="pending")
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(16), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    adjusted_close = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    bb_upper = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    atr_14 = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_market_snapshots_symbol_date", "symbol", "date", unique=True),
    )


class StockPick(Base):
    __tablename__ = "stock_picks"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    score = Column(Float, nullable=False)
    action = Column(Enum(TradeAction), nullable=False)
    confidence = Column(Float, nullable=False)
    forecast_return_4d = Column(Float, nullable=True)
    predicted_close_4d = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    max_hold_days = Column(Integer, default=4)
    reasoning = Column(Text, nullable=True)
    features = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True, index=True)
    exited_at = Column(DateTime, nullable=True)
    exit_return = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_stock_picks_active", "is_active", "run_date"),
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(16), nullable=False, index=True)
    side = Column(String(8), default="long", nullable=False)
    status = Column(Enum(PositionStatus), default=PositionStatus.open, nullable=False, index=True)

    # Entry
    entry_price = Column(Float, nullable=True)
    entry_date = Column(DateTime, default=datetime.utcnow, index=True)
    shares = Column(Float, nullable=True)
    notional = Column(Float, nullable=True)

    # Exit
    exit_price = Column(Float, nullable=True)
    exit_date = Column(DateTime, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    realized_return = Column(Float, nullable=True)

    # Plan
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    max_hold_days = Column(Integer, default=4)
    planned_exit_date = Column(DateTime, nullable=True)

    # Source
    stock_pick_id = Column(SQLUUID(as_uuid=True), ForeignKey("stock_picks.id"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock_pick = relationship("StockPick")
    orders = relationship("BrokerOrder", back_populates="position")

    __table_args__ = (
        Index("ix_paper_positions_status_symbol", "status", "symbol"),
        Index("ix_paper_positions_status_entry_date", "status", "entry_date"),
    )


class BrokerOrder(Base):
    __tablename__ = "broker_orders"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_id = Column(SQLUUID(as_uuid=True), ForeignKey("paper_positions.id"), nullable=True, index=True)
    broker = Column(String(32), default="alpaca", nullable=False)
    side = Column(String(8), nullable=False)  # buy or sell
    order_type = Column(String(16), nullable=False)  # market, limit, stop, oco
    symbol = Column(String(16), nullable=False, index=True)
    qty = Column(Float, nullable=True)
    notional = Column(Float, nullable=True)
    limit_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    broker_order_id = Column(String(64), nullable=True, index=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False, index=True)
    raw_response = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    position = relationship("PaperPosition", back_populates="orders")
