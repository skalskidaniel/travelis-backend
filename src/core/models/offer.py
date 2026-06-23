from datetime import date, datetime, time, timezone
from typing import Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from core.models.common import (
    CellId,
    IataCode,
    LocationPath,
    OfferId,
    PricePLN,
    Rating,
    ProviderName,
    BoardType,
)
from core.exceptions.provider import (
    DateMismatchException,
    DurationMismatchException,
    InvalidOfferMetadataException,
)

FRONTEND_URL_PREFIX = "https://wakacje-travelis.pl/"
SHARE_URL_PREFIX = f"{FRONTEND_URL_PREFIX}offer/"
REFERRAL_PARAMS = {
    "utm_source": "travellead",
    "utm_medium": "cps",
    "utm_campaign": "2933-t-HolidayPicker",
    "a_cid": "11111111",
    "a_aid": "2933",
}


class OfferSource(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    provider: ProviderName = Field(
        description="Provider that supplied this collapsed variant."
    )
    external_offer_id: str = Field(
        min_length=1, description="Provider-native offer identifier."
    )
    price_total: PricePLN = Field(
        description="Total trip price for this variant in PLN."
    )
    tour_operator: str | None = Field(
        default=None,
        description="Tour operator label when the provider exposes one (wakacje.pl dedup).",
    )


class WakacjePlMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    hotel_id: int = Field(
        ge=1, description="wakacje.pl hotelId for calculator/availability APIs."
    )
    tour_operator_id: int = Field(
        ge=1, description="wakacje.pl tourOperator (tourId in calculator payload)."
    )
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
    service_id: int = Field(
        ge=1, description="Raw wakacje.pl service (board) numeric code."
    )
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
    adults: int = Field(ge=1, description="Number of adults from the search cell.")
    children: int = Field(ge=0, description="Number of children from the search cell.")


class TuiMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_code: str = Field(
        min_length=1, description="TUI offerCode for hotel-cards availability checks."
    )


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
    wakacje_pl: WakacjePlMetadata | None = Field(
        default=None,
        description="Provider-specific ingest payload required for wakacje.pl availability checks.",
    )
    tui: TuiMetadata | None = Field(
        default=None,
        description="Provider-specific ingest payload required for tui.pl availability checks.",
    )


class RawOffer(BaseModel):
    """Provider-mapped offer row returned by an adapter before ingest normalization."""

    model_config = ConfigDict(strict=True, extra="forbid")

    provider: ProviderName
    external_offer_id: str = Field(
        min_length=1, description="Provider-native offer identifier."
    )
    hotel_name: str = Field(min_length=1, description="Display name of the hotel.")
    location: LocationPath
    departure_airport: IataCode
    departure_date: date = Field(description="Trip departure date.")
    return_date: date = Field(description="Trip return date.")
    duration: int = Field(ge=1, description="Trip length in nights.")
    board: BoardType
    stars: int = Field(ge=1, le=5, description="Hotel star rating.")
    rating: Rating
    review_count: int = Field(
        ge=0, description="Number of guest reviews backing the rating."
    )
    price_total: PricePLN
    price_per_day: PricePLN
    referral_url: AnyHttpUrl = Field(description="Provider deep link.")
    image_url: AnyHttpUrl | None = Field(
        default=None, description="Link for first offer image."
    )
    available: bool = Field(
        description="Whether the provider marks the offer as bookable."
    )
    room_type: str = Field(
        min_length=1, description="Normalized room type used for fingerprinting."
    )
    adults: int = Field(ge=1, description="Number of adults in the scrape occupancy.")
    children: int = Field(
        ge=0, description="Number of children in the scrape occupancy."
    )
    metadata: OfferMetadata = Field(
        description="Provider-specific metadata captured at ingest."
    )


class ScoredOffer(RawOffer):
    attractiveness_score: float = Field(
        ge=0,
        le=1,
        description="Stage-2 composite score used for feed sorting.",
    )


class Offer(ScoredOffer):
    cell_id: CellId = Field(description="Market cell this offer belongs to.")
    offer_id: OfferId
    share_url: HttpUrl = Field(
        description=f"Public share URL; must start with {SHARE_URL_PREFIX}",
    )
    scraped_at: datetime = Field(
        description="UTC timestamp when the offer was last scraped."
    )
    updated_at: datetime = Field(
        description="UTC timestamp when the offer row was last updated."
    )
    ttl: int = Field(
        ge=0, description="DynamoDB TTL as epoch seconds derived from departure_date."
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
            raise DateMismatchException(msg)

        night_span = (self.return_date - self.departure_date).days
        if abs(self.duration - night_span) > 1:
            msg = "duration must equal the number of nights between departure_date and return_date (+/- 1 day)"
            raise DurationMismatchException(msg)

        if (
            self.provider is ProviderName.WAKACJE_PL
            and self.metadata.wakacje_pl is None
        ):
            msg = "metadata.wakacje_pl is required for wakacje.pl offers"
            raise InvalidOfferMetadataException(msg)

        if self.provider is ProviderName.TUI:
            if self.metadata.tui is None:
                msg = "metadata.tui is required for tui offers"
                raise InvalidOfferMetadataException(msg)
            if self.external_offer_id != self.metadata.tui.offer_code:
                msg = "external_offer_id must match metadata.tui.offer_code"
                raise InvalidOfferMetadataException(msg)

        expected_ttl = int(
            datetime.combine(
                self.departure_date, time.min, tzinfo=timezone.utc
            ).timestamp()
        )
        if self.ttl != expected_ttl:
            msg = "ttl must equal departure_date epoch at 00:00:00 UTC"
            raise ValueError(msg)

        canonical_share_url = f"{SHARE_URL_PREFIX}{self.cell_id}/{self.offer_id}"
        self.share_url = type(self.share_url)(canonical_share_url)

        return self

    @field_validator("referral_url")
    @classmethod
    def append_referral_url(cls, value: HttpUrl) -> HttpUrl:
        url_str = str(value)
        parts = urlsplit(url_str)

        referral_qs = urlencode(REFERRAL_PARAMS, doseq=True)

        if parts.query and "=" not in parts.query:
            separator = "&" if parts.query else "?"
            new_query = (
                f"{parts.query}{separator}{referral_qs}" if parts.query else referral_qs
            )
            new_url = urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    new_query,
                    parts.fragment,
                )
            )
            return type(value)(new_url)

        params = dict(parse_qsl(parts.query, keep_blank_values=True))

        changed = False
        for key, val in REFERRAL_PARAMS.items():
            if params.get(key) != val:
                params[key] = val
                changed = True

        if not changed:
            return value

        new_query = urlencode(params, doseq=True)
        new_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                new_query,
                parts.fragment,
            )
        )

        return type(value)(new_url)
