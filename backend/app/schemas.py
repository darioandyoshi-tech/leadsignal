
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.models import Tier, SignalType, AlertChannel, SubscriptionStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserRead(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SubscriptionCreate(BaseModel):
    tier: Tier
    settings: Dict[str, Any] = {}


class SubscriptionRead(BaseModel):
    id: UUID
    tier: Tier
    status: SubscriptionStatus
    current_period_end: Optional[datetime]
    settings: Dict[str, Any]
    created_at: datetime


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    signal_type: SignalType
    severity: int
    headline: str
    summary: Optional[str]
    source_url: Optional[str]
    location_name: Optional[str]
    detected_at: datetime
    published_at: Optional[datetime]
    metadata_: Optional[Any] = Field(default=None, serialization_alias="metadata")

    @property
    def metadata(self) -> Optional[Any]:
        return self.metadata_


class SignalFilter(BaseModel):
    signal_type: Optional[SignalType] = None
    min_severity: int = 1
    city: Optional[str] = None
    zip_code: Optional[str] = None
    limit: int = 50
    offset: int = 0


class AlertPayload(BaseModel):
    channel: AlertChannel
    signal_ids: List[UUID]
    subscription_id: UUID


class CheckoutSessionRequest(BaseModel):
    tier: Tier
    success_url: str
    cancel_url: str
