import pytest
from decimal import Decimal
from datetime import date, datetime, timezone

from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, TuiMetadata
from core.repositories.offers import DynamoOffersRepository

pytestmark = pytest.mark.asyncio


# noinspection DuplicatedCode
@pytest.fixture
def test_offer():
    return Offer(
        provider=ProviderName.TUI,
        external_offer_id="TUI-OFFER-1",
        hotel_name="Test Hotel",
        location="Egipt/Hurghada/Hurghada City",
        departure_airport="WAW",
        departure_date=date(2026, 7, 12),
        return_date=date(2026, 7, 19),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=Decimal("4.5"),
        review_count=100,
        price_total=Decimal("5000.00"),
        price_per_day=Decimal("2500.00"),
        referral_url="https://www.tui.pl/details-eg-1",
        available=True,
        room_type="Family Room Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(
            tui=TuiMetadata(offer_code="TUI-OFFER-1"),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url="https://wakacje-travelis.pl/offer/123",
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783814400,
    )


async def test_offers_repo_lifecycle(offers_table, test_offer):
    repo = DynamoOffersRepository(offers_table)

    await repo.put(test_offer)
    fetched = await repo.get(test_offer.offer_id, cell_id=test_offer.cell_id)
    assert fetched is not None
    assert fetched.offer_id == test_offer.offer_id
    assert fetched.cell_id == test_offer.cell_id
    assert fetched.hotel_name == "Test Hotel"
    assert fetched.price_total == Decimal("5000.00")

    cell_offers = await repo.query_by_cell(test_offer.cell_id)
    assert len(cell_offers) == 1
    assert cell_offers[0].offer_id == test_offer.offer_id

    await repo.delete(test_offer.cell_id, test_offer.offer_id)
    assert await repo.get(test_offer.offer_id, cell_id=test_offer.cell_id) is None


async def test_offers_repo_batch_operations(offers_table, test_offer):
    repo = DynamoOffersRepository(offers_table)

    offer2 = test_offer.model_copy(
        update={"offer_id": "99999999999999999999999999999999"}
    )

    await repo.put_batch([test_offer, offer2])

    fetched1 = await repo.get(test_offer.offer_id, cell_id=test_offer.cell_id)
    fetched2 = await repo.get(offer2.offer_id, cell_id=offer2.cell_id)
    assert fetched1 is not None
    assert fetched2 is not None

    cell_offers = await repo.query_by_cell(test_offer.cell_id)
    assert len(cell_offers) == 2

    await repo.delete_batch(
        [
            (test_offer.cell_id, test_offer.offer_id),
            (offer2.cell_id, offer2.offer_id),
        ]
    )

    assert await repo.get(test_offer.offer_id, cell_id=test_offer.cell_id) is None
    assert await repo.get(offer2.offer_id, cell_id=offer2.cell_id) is None
