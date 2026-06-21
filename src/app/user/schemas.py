from datetime import date
from pydantic import BaseModel, ConfigDict, Field
from core.models.common import BoardType


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    countries: list[str] | None = Field(
        default=None,
        description="List of target countries for holiday search (e.g. ['Greece', 'Spain']).",
        examples=[["Greece", "Spain"]],
    )
    departure_airports: list[str] | None = Field(
        default=None,
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
    adults: int | None = Field(
        default=None,
        ge=1,
        description="Number of adult travelers.",
        examples=[2],
    )
    children: list[date] | None = Field(
        default=None,
        description="Birthdates of child travelers, used to calculate their age during the holiday.",
        examples=[["2018-05-12", "2021-11-20"]],
    )
    board: BoardType | None = Field(
        default=None,
        description="Catering/board option preference."
    )
    min_stars: int | None = Field(
        default=None,
        ge=2,
        le=5,
        description="Minimum hotel star rating (between 2 and 5).",
        examples=[4],
    )
    min_rating: int | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Minimum normalized guest rating (between 0 and 5).",
        examples=[4],
    )
    duration_min: int | None = Field(
        default=None,
        ge=2,
        description="Minimum trip duration in nights.",
        examples=[7],
    )
    duration_max: int | None = Field(
        default=None,
        description="Maximum trip duration in nights.",
        examples=[14],
    )


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
