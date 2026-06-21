from datetime import datetime, date, timezone
from pydantic import BaseModel, ConfigDict, Field

from core.models.common import BoardType


class UserPreferences(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    countries: list[str] = Field(
        default_factory=lambda: ["GR", "IT", "ES", "TR", "EG"],
        description="List of target countries for holiday search (e.g. ['Greece', 'Spain']).",
        examples=[["Greece", "Spain"]],
    )
    departure_airports: list[str] = Field(
        default_factory=list,
        description="List of departure airport IATA codes.",
        examples=[["WAW", "KRK"]],
    )
    date_from: date | None = Field(
        default=None,
        description="Earliest acceptable departure date.",
        examples=["2026-07-01"],
    )
    date_to: date | None = Field(
        default=None,
        description="Latest acceptable return date.",
        examples=["2026-08-31"],
    )
    adults: int = Field(
        default=2,
        ge=1,
        description="Number of adult travelers.",
        examples=[2],
    )
    children: list[date] = Field(
        default_factory=list,
        description="Birthdates of child travelers, used to calculate their age during the holiday.",
        examples=[["2018-05-12", "2021-11-20"]],
    )
    board: BoardType = Field(
        default=BoardType.ALL_INCLUSIVE,
        description="Catering/board option preference.",
    )
    min_stars: int = Field(
        default=2,
        ge=2,
        le=5,
        description="Minimum hotel star rating (between 2 and 5).",
        examples=[4],
    )
    min_rating: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Minimum normalized guest rating (between 0 and 5).",
        examples=[4],
    )
    duration_min: int = Field(
        default=5,
        ge=2,
        description="Minimum trip duration in nights.",
        examples=[7],
    )
    duration_max: int | None = Field(
        default=None,
        description="Maximum trip duration in nights.",
        examples=[14],
    )


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
