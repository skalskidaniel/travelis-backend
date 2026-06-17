from datetime import datetime, date, timezone
from pydantic import BaseModel, ConfigDict, Field

from core.models.common import BoardType


class UserPreferences(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    countries: list[str] = Field(default_factory=lambda: ["GR", "IT", "ES", "TR", "EG"])
    departure_airports: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    adults: int = Field(default=2, ge=1)
    children: list[date] = Field(default_factory=list)
    board: BoardType = Field(default=BoardType.ALL_INCLUSIVE)
    min_stars: int = Field(default=2, ge=2, le=5)
    min_rating: int = Field(default=0, ge=0, le=5)
    duration_min: int = Field(default=5, ge=2)
    duration_max: int | None = None


class PushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    endpoint: str
    keys: PushSubscriptionKeys


class User(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str = Field(description="Cognito sub identifier.")
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    push_enabled: bool = Field(default=False)
    push_subscription: PushSubscription | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
