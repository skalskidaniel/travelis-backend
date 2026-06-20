import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.coordinator import run_scrape_job
from core.container import Container
from core.models.cell import MarketCell
from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, RawOffer, TuiMetadata


@pytest.fixture
def mock_container():
    c = MagicMock(spec=Container)
    c.cells_repo = AsyncMock()
    c.offers_repo = AsyncMock()
    c.matching_service = AsyncMock()
    c.lambda_client = AsyncMock()
    c.settings = MagicMock()
    c.settings.lambda_function_arn = (
        "arn:aws:lambda:eu-central-1:123456789012:function:travelis-backend"
    )
    return c


@pytest.mark.asyncio
async def test_run_scrape_job_no_cells(mock_container):
    mock_container.cells_repo.scan.return_value = []

    result = await run_scrape_job(mock_container)
    assert result["scraped_cells"] == []
    assert result["matched_users"] == []
    assert result["continued"] is False


@pytest.mark.asyncio
async def test_run_scrape_job_successful(mock_container):
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

    # RawOffer mock results
    raw_tui = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-123",
        hotel_name="Sol Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_day=Decimal("142.86"),
        referral_url="https://tui.pl/ref",
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-123")),
    )

    # Mocking providers
    with (
        patch("app.jobs.coordinator.TuiProvider") as mock_tui_cls,
        patch("app.jobs.coordinator.WakacjePlProvider") as mock_wakacje_cls,
    ):
        mock_tui = mock_tui_cls.return_value
        mock_tui.search = AsyncMock(return_value=[raw_tui])
        mock_wakacje = mock_wakacje_cls.return_value
        mock_wakacje.search = AsyncMock(return_value=[])

        # Scorer mock
        with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
            mock_scorer = mock_get_scorer.return_value
            from core.models.offer import ScoredOffer

            scored_offer = ScoredOffer(
                **raw_tui.model_dump(), attractiveness_score=0.85
            )
            mock_scorer.score.return_value = [scored_offer]

            # Database calls mocks
            mock_container.offers_repo.query_by_cell.return_value = []
            mock_container.matching_service.bulk_match_users.return_value = ["user-1"]

            result = await run_scrape_job(mock_container)

            assert cell.cell_id in result["scraped_cells"]
            assert "user-1" in result["matched_users"]
            assert result["continued"] is False

            mock_container.offers_repo.put_batch.assert_called_once()
            mock_container.cells_repo.update_last_scraped.assert_called_once()
            mock_container.matching_service.bulk_match_users.assert_called_once_with(
                [cell.cell_id]
            )


@pytest.mark.asyncio
async def test_run_scrape_job_availability_by_absence(mock_container):
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

    # Raw scraped offer
    raw_scraped = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-new",
        hotel_name="Sol Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_day=Decimal("142.86"),
        referral_url="https://tui.pl/ref",
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-new")),
    )

    # Existing offer in DB for same cell (no longer present in scrape results)
    existing_offer = Offer(
        **raw_scraped.model_dump(),
        cell_id=cell.cell_id,
        offer_id="b" * 32,
        share_url="https://wakacje-travelis.pl/offer/dummy/dummy",
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783641600,
        attractiveness_score=0.5,
    )
    existing_offer.external_offer_id = "tui-existing"
    existing_offer.metadata.tui.offer_code = "tui-existing"

    with (
        patch("app.jobs.coordinator.TuiProvider") as mock_tui_cls,
        patch("app.jobs.coordinator.WakacjePlProvider") as mock_wakacje_cls,
    ):
        mock_tui = mock_tui_cls.return_value
        mock_tui.search = AsyncMock(return_value=[raw_scraped])
        mock_wakacje = mock_wakacje_cls.return_value
        mock_wakacje.search = AsyncMock(return_value=[])

        with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
            mock_scorer = mock_get_scorer.return_value
            from core.models.offer import ScoredOffer

            scored_offer = ScoredOffer(
                **raw_scraped.model_dump(), attractiveness_score=0.85
            )
            mock_scorer.score.return_value = [scored_offer]

            mock_container.offers_repo.query_by_cell.return_value = [existing_offer]

            await run_scrape_job(mock_container)

            # Check what was saved to the DB
            calls = mock_container.offers_repo.put_batch.call_args[0][0]
            # There should be 2 offers saved: new scraped (available=True) and existing (available=False)
            assert len(calls) == 2

            new_saved = next(o for o in calls if o.external_offer_id == "tui-new")
            assert new_saved.available is True

            existing_saved = next(
                o for o in calls if o.external_offer_id == "tui-existing"
            )
            assert existing_saved.available is False


@pytest.mark.asyncio
async def test_run_scrape_job_timeout_triggering(mock_container):
    cell1 = MarketCell(
        country="ES",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    cell2 = MarketCell(
        country="IT",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell1, cell2]

    mock_context = MagicMock()
    # Mock remaining time: first call returns 30000ms (worker can run), next return 5000ms (timeout!)
    mock_context.get_remaining_time_in_millis.side_effect = [
        30000,
        5000,
        5000,
        5000,
    ]

    raw_tui = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-1",
        hotel_name="Sol Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_day=Decimal("142.86"),
        referral_url="https://tui.pl/ref",
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-1")),
    )

    with (
        patch("app.jobs.coordinator.TuiProvider") as mock_tui_cls,
        patch("app.jobs.coordinator.WakacjePlProvider") as mock_wakacje_cls,
    ):
        mock_tui = mock_tui_cls.return_value
        mock_tui.search = AsyncMock(return_value=[raw_tui])
        mock_wakacje = mock_wakacje_cls.return_value
        mock_wakacje.search = AsyncMock(return_value=[])

        with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
            mock_scorer = mock_get_scorer.return_value
            from core.models.offer import ScoredOffer

            scored_offer = ScoredOffer(
                **raw_tui.model_dump(), attractiveness_score=0.85
            )
            mock_scorer.score.return_value = [scored_offer]

            mock_container.offers_repo.query_by_cell.return_value = []

            result = await run_scrape_job(mock_container, context=mock_context)

            assert result["continued"] is True
            # Verification: lambda client should have been invoked to trigger continuation
            mock_container.lambda_client.invoke.assert_called_once()
            payload = json.loads(
                mock_container.lambda_client.invoke.call_args[1]["Payload"]
            )
            assert payload["type"] == "scrape_offers"
            # cell2 should be in remaining_cells since we halted before processing it
            assert cell2.cell_id in payload["remaining_cells"]


@pytest.mark.asyncio
async def test_run_scrape_job_retries_exponential(mock_container):
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

    with (
        patch("app.jobs.coordinator.TuiProvider") as mock_tui_cls,
        patch("app.jobs.coordinator.WakacjePlProvider") as mock_wakacje_cls,
    ):
        mock_tui = mock_tui_cls.return_value
        # Fail 2 times, then succeed with empty list
        mock_tui.search = AsyncMock(
            side_effect=[Exception("Timeout"), Exception("Timeout"), []]
        )
        mock_wakacje = mock_wakacje_cls.return_value
        mock_wakacje.search = AsyncMock(return_value=[])

        await run_scrape_job(mock_container)

        assert mock_tui.search.call_count == 3
