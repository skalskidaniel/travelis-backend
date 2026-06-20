from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from core.models.common import ProviderName, BoardType
from core.models.offer import Offer, OfferSource


class OfferFeedItem(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str
    hotel_name: str
    location: str
    country: str
    departure_airport: str
    departure_date: date
    return_date: date
    duration: int
    board: BoardType
    stars: int
    rating: float
    review_count: int
    price_total: Decimal
    referral_url: str
    image_url: str | None
    share_url: str

    @classmethod
    def from_domain(cls, offer: Offer) -> "OfferFeedItem":
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
            referral_url=str(offer.referral_url),
            image_url=str(offer.image_url) if offer.image_url else None,
            share_url=str(offer.share_url),
        )


class OfferDetailResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str
    provider: ProviderName
    external_offer_id: str
    hotel_name: str
    location: str
    country: str
    region: str
    departure_airport: str
    departure_date: date
    return_date: date
    duration: int
    board: BoardType
    stars: int
    rating: float
    review_count: int
    price_total: Decimal
    price_per_day: Decimal
    attractiveness_score: float
    available: bool
    referral_url: str
    image_url: str | None
    share_url: str
    sources: list[OfferSource]
    scraped_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, offer: Offer) -> "OfferDetailResponse":
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
            price_per_day=offer.price_per_day,
            attractiveness_score=offer.attractiveness_score,
            available=offer.available,
            referral_url=str(offer.referral_url),
            image_url=str(offer.image_url) if offer.image_url else None,
            share_url=str(offer.share_url),
            sources=offer.metadata.sources,
            scraped_at=offer.scraped_at,
            updated_at=offer.updated_at,
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
