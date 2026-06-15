
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
