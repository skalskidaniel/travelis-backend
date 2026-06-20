from datetime import date
from pydantic import BaseModel, ConfigDict, Field
from core.models.common import BoardType


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    countries: list[str] | None = Field(default=None)
    departure_airports: list[str] | None = Field(default=None)
    date_from: date | None = Field(default=None)
    date_to: date | None = Field(default=None)
    adults: int | None = Field(default=None, ge=1)
    children: list[date] | None = Field(default=None)
    board: BoardType | None = Field(default=None)
    min_stars: int | None = Field(default=None, ge=2, le=5)
    min_rating: int | None = Field(default=None, ge=0, le=5)
    duration_min: int | None = Field(default=None, ge=2)
    duration_max: int | None = Field(default=None)


class PushSubscriptionKeysSchema(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    p256dh: str
    auth: str


class PushSubscriptionSchema(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    endpoint: str
    keys: PushSubscriptionKeysSchema


class PushEnableRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    subscription: PushSubscriptionSchema
