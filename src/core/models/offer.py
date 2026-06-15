from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PlainValidator,
    field_validator,
    model_validator,
)

HEX_CELL_ID = r"^[a-f0-9]{16}$"
HEX_OFFER_ID = r"^[a-f0-9]{32}$"
IATA_CODE = r"^[A-Z]{3}$"
LOCATION_PATH = r"^[^/]+/[^/]+/[^/]+$"
SHARE_URL_PREFIX = "https://wakacje-travelis.pl/"


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class Provider(StrEnum):
    WAKACJE = "wakacje"
    TUI = "tui"


class BoardType(StrEnum):
    ALL_INCLUSIVE = "all-inclusive"
    FULL_BOARD = "full-board"
    HALF_BOARD = "half-board"
    BED_AND_BREAKFAST = "bed-and-breakfast"
    NONE = "none"


CellId = Annotated[
    str,
    Field(
        pattern=HEX_CELL_ID,
        description="Deterministic hash of market-cell dimensions (first 16 hex chars of SHA-256).",
    ),
]

OfferId = Annotated[
    str,
    Field(
        pattern=HEX_OFFER_ID,
        description="Semantic fingerprint hash of trip semantics (first 32 hex chars of SHA-256).",
    ),
]

IataCode = Annotated[
    str,
    Field(
        pattern=IATA_CODE,
        description="Departure airport IATA code (uppercase).",
    ),
]

LocationPath = Annotated[
    str,
    Field(
        pattern=LOCATION_PATH,
        description="Normalized location as Country/Region/City.",
    ),
]

PricePLN = Annotated[
    Decimal,
    PlainValidator(_to_decimal),
    Field(
        ge=Decimal(0),
        decimal_places=2,
        description="Monetary amount in PLN (up to two decimal places).",
    ),
]

Rating = Annotated[
    Decimal,
    PlainValidator(_to_decimal),
    Field(
        ge=Decimal(0),
        le=Decimal(5),
        decimal_places=1,
        description="Canonical hotel rating on a 0–5 scale (one decimal place).",
    ),
]


class OfferSource(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    provider: Provider = Field(description="Provider that supplied this collapsed variant.")
    provider_id: str = Field(min_length=1, description="Provider-native offer identifier.")
    price_total: PricePLN = Field(description="Total trip price for this variant in PLN.")
    tour_operator: str | None = Field(
        default=None,
        description="Tour operator label when the provider exposes one (wakacje.pl dedup).",
    )


class WakacjeMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    hotel_id: int = Field(ge=1, description="wakacje.pl hotelId for calculator/availability APIs.")
    tour_operator_id: int = Field(ge=1, description="wakacje.pl tourOperator (tourId in calculator payload).")
    tour_op_code: str | None = Field(
        default=None,
        min_length=1,
        description="wakacje.pl tourOpCode when present on the search response.",
    )
    country_id: int = Field(ge=1, description="wakacje.pl place.country.id.")
    region_id: int = Field(ge=1, description="wakacje.pl place.region.id.")
    city_id: int = Field(ge=1, description="wakacje.pl place.city.id.")
    departure_city_id: int = Field(
        ge=1,
        description="wakacje.pl departure city id mapped from departurePlace (not the IATA code).",
    )
    service_id: int = Field(ge=1, description="Raw wakacje.pl service (board) numeric code.")
    transport_id: int = Field(
        default=1,
        ge=1,
        description="wakacje.pl departureType; 1 = flight.",
    )
    departure_slug: str = Field(
        min_length=1,
        description="URL slug derived from departurePlace (e.g. z-wroclawia).",
    )
    offer_page_path: str = Field(
        min_length=1,
        pattern=r"^/.+",
        description="Relative offer page path used as Referer on wakacje.pl API calls.",
    )


class TuiMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_code: str = Field(min_length=1, description="TUI offerCode for hotel-cards availability checks.")


class OfferMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    price_z_score: float | None = Field(
        default=None,
        description="Stage-1 price z-score retained for debugging and attractiveness scoring.",
    )
    sources: list[OfferSource] = Field(
        default_factory=list,
        description="Collapsed provider variants after deduplication (lowest price wins at offer level).",
    )
    wakacje: WakacjeMetadata | None = Field(
        default=None,
        description="Provider-specific ingest payload required for wakacje.pl availability checks.",
    )
    tui: TuiMetadata | None = Field(
        default=None,
        description="Provider-specific ingest payload required for tui.pl availability checks.",
    )


class Offer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    cell_id: CellId = Field(description="Market cell this offer belongs to.")
    offer_id: OfferId = Field(description="Globally unique semantic fingerprint for the trip.")
    provider: Provider = Field(description="Source provider adapter (wakacje or tui).")
    provider_id: str = Field(
        min_length=1,
        description="Provider-native ID (wakacje offerId or TUI offerCode).",
    )
    hotel_name: str = Field(min_length=1, description="Display name of the hotel.")
    location: LocationPath = Field(description="Normalized Country/Region/City location path.")
    departure_airport: IataCode = Field(description="Departure airport IATA code.")
    departure_date: date = Field(description="Trip departure date (ISO calendar date).")
    return_date: date = Field(description="Trip return date (ISO calendar date).")
    duration: int = Field(ge=1, description="Trip length in nights.")
    board: BoardType = Field(description="Normalized board type.")
    stars: int = Field(ge=1, le=5, description="Hotel star rating.")
    rating: Rating = Field(description="Canonical guest rating on a 0–5 scale.")
    review_count: int = Field(ge=0, description="Number of guest reviews backing the rating.")
    price_total: PricePLN = Field(description="Total trip price in PLN.")
    price_per_day_one_person: PricePLN = Field(
        description="PLN per night per person: price_total / duration / (adults + children).",
    )
    attractiveness_score: float = Field(
        ge=0,
        le=1,
        description="Stage-2 composite score used for feed sorting.",
    )
    referral_url: AnyHttpUrl = Field(description="Provider or travellead deep link.")
    share_url: HttpUrl = Field(
        description=f"Public share URL; must start with {SHARE_URL_PREFIX}",
    )
    scraped_at: datetime = Field(description="UTC timestamp when the offer was last scraped.")
    updated_at: datetime = Field(description="UTC timestamp when the offer row was last updated.")
    available: bool = Field(description="Whether the offer is currently bookable.")
    ttl: int = Field(ge=0, description="DynamoDB TTL as epoch seconds derived from departure_date.")
    metadata: OfferMetadata = Field(
        description="Internal/debug fields not surfaced in the user feed.",
    )

    @field_validator("share_url")
    @classmethod
    def share_url_uses_frontend_prefix(cls, value: HttpUrl) -> HttpUrl:
        if not str(value).startswith(SHARE_URL_PREFIX):
            msg = f"share_url must start with {SHARE_URL_PREFIX}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_trip_dates_and_provider_metadata(self) -> Self:
        if self.return_date < self.departure_date:
            msg = "return_date must be on or after departure_date"
            raise ValueError(msg)

        night_span = (self.return_date - self.departure_date).days
        if self.duration != night_span:
            msg = "duration must equal the number of nights between departure_date and return_date"
            raise ValueError(msg)

        if self.provider is Provider.WAKACJE and self.metadata.wakacje is None:
            msg = "metadata.wakacje is required for wakacje offers"
            raise ValueError(msg)

        if self.provider is Provider.TUI:
            if self.metadata.tui is None:
                msg = "metadata.tui is required for tui offers"
                raise ValueError(msg)
            if self.provider_id != self.metadata.tui.offer_code:
                msg = "provider_id must match metadata.tui.offer_code"
                raise ValueError(msg)

        return self
