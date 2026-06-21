from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from core.models.common import BoardType


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    countries: list[str] | None = Field(
        default=None,
        max_length=20,
        description="List of target country ISO 3166-1 alpha-2 codes (e.g. ['GR', 'ES']).",
        examples=[["GR", "ES"]],
    )
    departure_airports: list[str] | None = Field(
        default=None,
        max_length=17,
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
        le=6,
        description="Number of adult travelers. Total occupants (adults + children) cannot exceed 8.",
        examples=[2],
    )
    children: list[date] | None = Field(
        default=None,
        max_length=5,
        description="Birthdates of child travelers, used to calculate their age during the holiday. Total occupants (adults + children) cannot exceed 8.",
        examples=[["2018-05-12", "2021-11-20"]],
    )
    board: BoardType | None = Field(
        default=None, description="Catering/board option preference."
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

    @field_validator("countries")
    @classmethod
    def validate_countries_are_supported(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        from core.models.cell import _allowed_country_codes

        allowed = _allowed_country_codes()
        for code in value:
            if code not in allowed:
                raise ValueError(f"Unsupported country code '{code}'")
        return value

    @field_validator("departure_airports")
    @classmethod
    def validate_departure_airports_format(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        import re

        iata_pattern = re.compile(r"^[A-Z]{3}$")
        for airport in value:
            if not iata_pattern.match(airport):
                raise ValueError(
                    f"Invalid departure airport code '{airport}'; must be a 3-letter uppercase IATA code."
                )
        return value

    @model_validator(mode="after")
    def validate_preferences_update_cross_fields(self) -> "UserPreferencesUpdate":
        if self.date_from is not None and self.date_to is not None:
            if self.date_to < self.date_from:
                raise ValueError("date_to must be on or after date_from")

        if self.duration_max is not None and self.duration_min is not None:
            if self.duration_max < self.duration_min:
                raise ValueError(
                    "duration_max must be greater than or equal to duration_min"
                )

        if self.adults is not None and self.children is not None:
            total_occupants = self.adults + len(self.children)
            if total_occupants > 8:
                raise ValueError(
                    f"Total occupants (adults + children) cannot exceed 8. Current: {total_occupants}"
                )

        return self


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
