from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.availability import run_availability_job
from core.container import Container
from core.models.cell import MarketCell
from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, TuiMetadata


@pytest.fixture
def mock_container():
    c = MagicMock(spec=Container)
    c.cells_repo = AsyncMock()
    c.offers_repo = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_run_availability_job_no_cells(mock_container):
    mock_container.cells_repo.scan.return_value = []
    result = await run_availability_job(mock_container)
    assert result["checked_offers_count"] == 0
    assert result["updated_offers_count"] == 0


@pytest.mark.asyncio
async def test_run_availability_job_nothing_available(mock_container):
    cell = MarketCell(
        country="ES",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    # Offer that is already unavailable
    metadata = OfferMetadata(
        price_z_score=0.5, sources=[], tui=TuiMetadata(offer_code="ext-123")
    )
    offer = Offer(
        cell_id=cell.cell_id,
        offer_id="a" * 32,
        attractiveness_score=0.9,
        provider=ProviderName.TUI,
        external_offer_id="ext-123",
        hotel_name="H1",
        location="ES/M/C",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=4.0,
        review_count=50,
        price_total=Decimal("1000"),
        price_per_day=Decimal("71.43"),
        referral_url="https://tui.pl/ref",
        available=False,
        room_type="Standard",
        adults=2,
        children=0,
        share_url="https://wakacje-travelis.pl/offer/dummy/dummy",
        metadata=metadata,
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783641600,
    )
    mock_container.offers_repo.query_by_cell.return_value = [offer]

    result = await run_availability_job(mock_container)
    assert result["checked_offers_count"] == 0
    assert result["updated_offers_count"] == 0
    mock_container.offers_repo.put.assert_not_called()


@pytest.mark.asyncio
async def test_run_availability_job_becomes_unavailable(mock_container):
    cell = MarketCell(
        country="ES",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    metadata = OfferMetadata(
        price_z_score=0.5, sources=[], tui=TuiMetadata(offer_code="ext-123")
    )
    offer = Offer(
        cell_id=cell.cell_id,
        offer_id="a" * 32,
        attractiveness_score=0.9,
        provider=ProviderName.TUI,
        external_offer_id="ext-123",
        hotel_name="H1",
        location="ES/M/C",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=4.0,
        review_count=50,
        price_total=Decimal("1000"),
        price_per_day=Decimal("71.43"),
        referral_url="https://tui.pl/ref",
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        share_url="https://wakacje-travelis.pl/offer/dummy/dummy",
        metadata=metadata,
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783641600,
    )
    mock_container.offers_repo.query_by_cell.return_value = [offer]

    with patch("app.jobs.availability.TuiProvider") as mock_tui_cls:
        mock_tui = mock_tui_cls.return_value
        mock_tui.check_availability = AsyncMock(return_value=False)  # unavailable

        result = await run_availability_job(mock_container)

        assert result["checked_offers_count"] == 1
        assert result["updated_offers_count"] == 1

        mock_container.offers_repo.put.assert_called_once()
        saved_offer = mock_container.offers_repo.put.call_args[0][0]
        assert saved_offer.available is False


@pytest.mark.asyncio
async def test_run_availability_job_price_updates(mock_container):
    cell = MarketCell(
        country="ES",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    metadata = OfferMetadata(
        price_z_score=0.5, sources=[], tui=TuiMetadata(offer_code="ext-123")
    )
    offer = Offer(
        cell_id=cell.cell_id,
        offer_id="a" * 32,
        attractiveness_score=0.9,
        provider=ProviderName.TUI,
        external_offer_id="ext-123",
        hotel_name="H1",
        location="ES/M/C",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=4.0,
        review_count=50,
        price_total=Decimal("1000"),
        price_per_day=Decimal("71.43"),
        referral_url="https://tui.pl/ref",
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        share_url="https://wakacje-travelis.pl/offer/dummy/dummy",
        metadata=metadata,
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783641600,
    )
    mock_container.offers_repo.query_by_cell.return_value = [offer]

    with patch("app.jobs.availability.TuiProvider") as mock_tui_cls:
        mock_tui = mock_tui_cls.return_value
        mock_tui.check_availability = AsyncMock(return_value=True)  # still available
        mock_tui.check_price = AsyncMock(return_value=Decimal("1200"))  # price changed

        result = await run_availability_job(mock_container)

        assert result["checked_offers_count"] == 1
        assert result["updated_offers_count"] == 1

        mock_container.offers_repo.put.assert_called_once()
        saved_offer = mock_container.offers_repo.put.call_args[0][0]
        assert saved_offer.available is True
        assert saved_offer.price_total == Decimal("1200")
        assert saved_offer.price_per_day == Decimal("85.71")
