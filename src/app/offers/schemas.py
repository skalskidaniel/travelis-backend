from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from core.models.common import ProviderName, BoardType
from core.models.offer import Offer, OfferSource


class OfferFeedItem(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str = Field(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    )
    hotel_name: str = Field(
        description="The display name of the hotel.",
        examples=["Seaside Resort & Spa"],
    )
    location: str = Field(
        description="Normalized location path formatted as Country/Region/City.",
        examples=["Greece/Crete/Chania"],
    )
    country: str = Field(
        description="Country derived from the location path.",
        examples=["Greece"],
    )
    departure_airport: str = Field(
        description="IATA airport code of departure.",
        examples=["WAW"],
    )
    departure_date: date = Field(
        description="Trip departure date.",
        examples=["2026-07-15"],
    )
    return_date: date = Field(
        description="Trip return date.",
        examples=["2026-07-22"],
    )
    duration: int = Field(
        description="Number of nights for the trip.",
        examples=[7],
    )
    board: BoardType = Field(description="The board/catering type offered.")
    stars: int = Field(
        description="Hotel star rating (from 1 to 5).",
        ge=1,
        le=5,
        examples=[4],
    )
    rating: float = Field(
        description="Average guest rating normalized on a 0–5 scale.",
        ge=0.0,
        le=5.0,
        examples=[4.5],
    )
    review_count: int = Field(
        description="Total number of reviews backing the rating.",
        ge=0,
        examples=[342],
    )
    price_total: Decimal = Field(
        description="Total cost of the trip for all travelers in PLN.",
        examples=[Decimal("2450.00")],
    )
    price_per_person: Decimal = Field(
        description="Total trip cost per traveler in PLN.",
        examples=[Decimal("1225.00")],
    )
    referral_url: str = Field(
        description="Affiliate/referral deep link to the provider page.",
        examples=[
            "https://www.wakacje.pl/oferty/grecja/kreta/hotel-seaside-resort-123456.html?utm_source=travellead"
        ],
    )
    image_url: str | None = Field(
        default=None,
        description="Direct URL to the main preview image of the hotel.",
        examples=["https://images.travelis.pl/hotels/123456_main.jpg"],
    )
    share_url: str = Field(
        description="Public URL used for sharing this offer with other users.",
        examples=[
            "https://wakacje-travelis.pl/offer/1f2e3d4c5b6a7f8e/4a8b9c1d2e3f4051627384950a1b2c3d"
        ],
    )
    favorited: bool = Field(
        default=False,
        description="Flag indicating if this offer is favorited by the user.",
    )

    @classmethod
    def from_domain(cls, offer: Offer, favorited: bool = False) -> "OfferFeedItem":
        parts = offer.location.split("/")
        country = parts[0] if len(parts) > 0 else ""

        return cls(
            offer_id=offer.offer_id,
            hotel_name=offer.hotel_name,
            location=offer.location,
            country=country,
            departure_airport=offer.departure_airport,
            departure_date=offer.departure_date,
            return_date=offer.return_date,
            duration=offer.duration,
            board=offer.board,
            stars=offer.stars,
            rating=float(offer.rating),
            review_count=offer.review_count,
            price_total=offer.price_total,
            price_per_person=offer.price_per_person,
            referral_url=str(offer.referral_url),
            image_url=str(offer.image_url) if offer.image_url else None,
            share_url=str(offer.share_url),
            favorited=favorited,
        )


class OfferDetailResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str = Field(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    )
    provider: ProviderName = Field(
        description="Name of the provider who supplied the offer."
    )
    external_offer_id: str = Field(
        description="Provider-native unique identifier for the offer.",
        examples=["wakacje-99887766"],
    )
    hotel_name: str = Field(
        description="The display name of the hotel.",
        examples=["Seaside Resort & Spa"],
    )
    location: str = Field(
        description="Normalized location path formatted as Country/Region/City.",
        examples=["Greece/Crete/Chania"],
    )
    country: str = Field(
        description="Country derived from the location path.",
        examples=["Greece"],
    )
    region: str = Field(
        description="Region derived from the location path.",
        examples=["Crete"],
    )
    departure_airport: str = Field(
        description="IATA airport code of departure.",
        examples=["WAW"],
    )
    departure_date: date = Field(
        description="Trip departure date.",
        examples=["2026-07-15"],
    )
    return_date: date = Field(
        description="Trip return date.",
        examples=["2026-07-22"],
    )
    duration: int = Field(
        description="Number of nights for the trip.",
        examples=[7],
    )
    board: BoardType = Field(description="The board/catering type offered.")
    stars: int = Field(
        description="Hotel star rating (from 1 to 5).",
        ge=1,
        le=5,
        examples=[4],
    )
    rating: float = Field(
        description="Average guest rating normalized on a 0–5 scale.",
        ge=0.0,
        le=5.0,
        examples=[4.5],
    )
    review_count: int = Field(
        description="Total number of reviews backing the rating.",
        ge=0,
        examples=[342],
    )
    price_total: Decimal = Field(
        description="Total cost of the trip for all travelers in PLN.",
        examples=[Decimal("2450.00")],
    )
    price_per_person: Decimal = Field(
        description="Total trip cost per traveler in PLN.",
        examples=[Decimal("1225.00")],
    )
    price_per_day: Decimal = Field(
        description="Average price per person per day in PLN.",
        examples=[Decimal("350.00")],
    )
    attractiveness_score: float = Field(
        description="Calculated composite attractiveness score between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
        examples=[0.87],
    )
    available: bool = Field(
        description="Flag indicating if the offer is currently bookable/available.",
        examples=[True],
    )
    referral_url: str = Field(
        description="Affiliate/referral deep link to the provider page.",
        examples=[
            "https://www.wakacje.pl/oferty/grecja/kreta/hotel-seaside-resort-123456.html?utm_source=travellead"
        ],
    )
    image_url: str | None = Field(
        default=None,
        description="Direct URL to the main preview image of the hotel.",
        examples=["https://images.travelis.pl/hotels/123456_main.jpg"],
    )
    share_url: str = Field(
        description="Public URL used for sharing this offer with other users.",
        examples=[
            "https://wakacje-travelis.pl/offer/1f2e3d4c5b6a7f8e/4a8b9c1d2e3f4051627384950a1b2c3d"
        ],
    )
    favorited: bool = Field(
        default=False,
        description="Flag indicating if this offer is favorited by the user.",
    )
    sources: list[OfferSource] = Field(
        description="List of raw source offers that were merged to form this offer."
    )
    scraped_at: datetime = Field(
        description="The timestamp when the offer was originally scraped.",
        examples=[datetime(2026, 6, 21, 12, 0, 0)],
    )
    updated_at: datetime = Field(
        description="The timestamp when the offer record was last updated.",
        examples=[datetime(2026, 6, 21, 14, 30, 0)],
    )

    @classmethod
    def from_domain(
        cls, offer: Offer, favorited: bool = False
    ) -> "OfferDetailResponse":
        parts = offer.location.split("/")
        country = parts[0] if len(parts) > 0 else ""
        region = parts[1] if len(parts) > 1 else ""

        return cls(
            offer_id=offer.offer_id,
            provider=offer.provider,
            external_offer_id=offer.external_offer_id,
            hotel_name=offer.hotel_name,
            location=offer.location,
            country=country,
            region=region,
            departure_airport=offer.departure_airport,
            departure_date=offer.departure_date,
            return_date=offer.return_date,
            duration=offer.duration,
            board=offer.board,
            stars=offer.stars,
            rating=float(offer.rating),
            review_count=offer.review_count,
            price_total=offer.price_total,
            price_per_person=offer.price_per_person,
            price_per_day=offer.price_per_day,
            attractiveness_score=offer.attractiveness_score,
            available=offer.available,
            referral_url=str(offer.referral_url),
            image_url=str(offer.image_url) if offer.image_url else None,
            share_url=str(offer.share_url),
            sources=offer.metadata.sources,
            scraped_at=offer.scraped_at,
            updated_at=offer.updated_at,
            favorited=favorited,
        )


class PaginatedOffersResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offers: list[OfferFeedItem] = Field(description="A page of offers.")
    next_cursor: str | None = Field(
        default=None, description="Cursor for fetching the next page."
    )
    feed_version: int | None = Field(
        default=None, description="The version of the feed used for pagination."
    )
    total_count: int = Field(
        description="The total number of matched offers available in the feed."
    )
