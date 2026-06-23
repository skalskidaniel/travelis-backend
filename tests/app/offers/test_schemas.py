from datetime import date, datetime, timezone
from decimal import Decimal
from pydantic import HttpUrl, ValidationError
import pytest

from core.models.common import ProviderName, BoardType
from core.models.offer import Offer, OfferMetadata, OfferSource, TuiMetadata
from app.offers.schemas import (
    PaginatedOffersResponse,
    OfferFeedItem,
    OfferDetailResponse,
)


@pytest.fixture
def sample_domain_offer() -> Offer:
    metadata = OfferMetadata(
        price_z_score=0.5,
        sources=[
            OfferSource(
                provider=ProviderName.TUI,
                external_offer_id="ext-123",
                price_total=Decimal("1000.00"),
            )
        ],
        tui=TuiMetadata(offer_code="ext-123"),
    )
    return Offer(
        cell_id="1a2b3c4d5e6f7a8b",
        offer_id="1a2b3c4d5e6f7a8b1a2b3c4d5e6f7a8b",
        attractiveness_score=0.92,
        provider=ProviderName.TUI,
        external_offer_id="ext-123",
        hotel_name="Test Hotel",
        location="Greece/Crete/Ierapetra",
        departure_airport="WAW",
        departure_date=date(2026, 6, 20),
        return_date=date(2026, 6, 27),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=4.5,
        review_count=100,
        price_total=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=HttpUrl("https://tui.pl/ref"),
        image_url=HttpUrl("https://tui.pl/img.jpg"),
        share_url=HttpUrl(
            "https://wakacje-travelis.pl/offer/1a2b3c4d5e6f7a8b/1a2b3c4d5e6f7a8b1a2b3c4d5e6f7a8b"
        ),
        available=True,
        room_type="Double Room",
        adults=2,
        children=0,
        metadata=metadata,
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1781913600,
    )


def test_offer_feed_item_from_domain(sample_domain_offer):
    feed_item = OfferFeedItem.from_domain(sample_domain_offer)
    assert feed_item.offer_id == sample_domain_offer.offer_id
    assert feed_item.country == "Greece"
    assert feed_item.location == "Greece/Crete/Ierapetra"
    assert not hasattr(feed_item, "metadata")


def test_offer_detail_response_from_domain(sample_domain_offer):
    detail = OfferDetailResponse.from_domain(sample_domain_offer)
    assert detail.offer_id == sample_domain_offer.offer_id
    assert detail.country == "Greece"
    assert detail.region == "Crete"
    assert detail.location == "Greece/Crete/Ierapetra"
    assert detail.sources == sample_domain_offer.metadata.sources
    assert not hasattr(detail, "metadata")


def test_paginated_offers_response_valid():
    response = PaginatedOffersResponse(
        offers=[],
        next_cursor="cursor-123",
        feed_version=1,
        total_count=0,
    )
    assert response.offers == []
    assert response.next_cursor == "cursor-123"
    assert response.feed_version == 1
    assert response.total_count == 0


def test_paginated_offers_response_invalid_types():
    with pytest.raises(ValidationError):
        PaginatedOffersResponse(
            offers="not-a-list",
            next_cursor=123,
            feed_version="not-an-int",
            total_count="not-an-int",
        )
