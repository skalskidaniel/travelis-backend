import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pydantic import AnyHttpUrl, HttpUrl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.coordinator import is_cell_month_past, run_scrape_job
from core.container import Container
from core.models.cell import MarketCell
from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, RawOffer, ScoredOffer, TuiMetadata
from core.services.ingest import compute_offer_id


@pytest.fixture
def mock_container():
    c = MagicMock(spec=Container)
    c.cells_repo = AsyncMock()
    c.offers_repo = AsyncMock()
    c.matching_service = AsyncMock()
    c.lambda_client = AsyncMock()
    c.tui_provider = MagicMock()
    c.wakacje_provider = MagicMock()
    c.settings = MagicMock()
    c.settings.lambda_function_arn = (
        "arn:aws:lambda:eu-central-1:123456789012:function:travelis-backend"
    )
    c.settings.scoring = MagicMock()
    c.settings.scoring.attractiveness_z_threshold = -1.0
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
        month="2027-07",
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
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_person=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=AnyHttpUrl("https://tui.pl/ref"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-123")),
    )

    # Mocking providers
    mock_container.tui_provider.search = AsyncMock(return_value=[raw_tui])
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    # Scorer mock
    with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
        mock_scorer = mock_get_scorer.return_value
        scored_offer: ScoredOffer = ScoredOffer(
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
        month="2027-07",
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
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_person=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=AnyHttpUrl("https://tui.pl/ref"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-new")),
    )

    # Existing offer in DB for same cell (no longer present in scrape results)
    existing_offer: Offer = Offer(
        **raw_scraped.model_dump(),
        cell_id=cell.cell_id,
        offer_id="b" * 32,
        share_url=HttpUrl("https://wakacje-travelis.pl/offer/dummy/dummy"),
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1815177600,
        attractiveness_score=0.5,
    )
    existing_offer.external_offer_id = "tui-existing"
    assert existing_offer.metadata.tui is not None
    existing_offer.metadata.tui.offer_code = "tui-existing"

    mock_container.tui_provider.search = AsyncMock(return_value=[raw_scraped])
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
        mock_scorer = mock_get_scorer.return_value

        scored_offer: ScoredOffer = ScoredOffer(
            **raw_scraped.model_dump(), attractiveness_score=0.85
        )
        mock_scorer.score.return_value = [scored_offer]

        mock_container.offers_repo.query_by_cell.return_value = [existing_offer]
        mock_container.offers_repo.delete_batch = AsyncMock()

        await run_scrape_job(mock_container)

        calls = mock_container.offers_repo.put_batch.call_args[0][0]
        assert len(calls) == 2

        new_saved = next(o for o in calls if o.external_offer_id == "tui-new")
        assert new_saved.available is True

        soft_deleted = next(o for o in calls if o.offer_id == existing_offer.offer_id)
        assert soft_deleted.available is False
        assert soft_deleted.ttl != existing_offer.ttl

        mock_container.offers_repo.delete_batch.assert_not_called()


@pytest.mark.asyncio
async def test_run_scrape_job_timeout_triggering(mock_container):
    cell1 = MarketCell(
        country="ES",
        month="2027-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    cell2 = MarketCell(
        country="IT",
        month="2027-07",
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
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_person=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=AnyHttpUrl("https://tui.pl/ref"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-1")),
    )

    mock_container.tui_provider.search = AsyncMock(return_value=[raw_tui])
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
        mock_scorer = mock_get_scorer.return_value

        scored_offer: ScoredOffer = ScoredOffer(
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
        month="2027-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    # Fail 2 times, then succeed with empty list
    mock_container.tui_provider.search = AsyncMock(
        side_effect=[Exception("Timeout"), Exception("Timeout"), []]
    )
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    await run_scrape_job(mock_container)

    assert mock_container.tui_provider.search.call_count == 3


@pytest.mark.asyncio
async def test_run_scrape_job_skips_cell_when_all_scored_offers_fail_validation(
    mock_container,
):
    cell = MarketCell(
        country="ES",
        month="2027-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    raw_tui = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-invalid",
        hotel_name="Sol Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_person=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=AnyHttpUrl("https://tui.pl/ref"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-invalid")),
    )

    mock_container.tui_provider.search = AsyncMock(return_value=[raw_tui])
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
        mock_scorer = mock_get_scorer.return_value

        scored_offer: ScoredOffer = ScoredOffer(
            **raw_tui.model_dump(), attractiveness_score=0.85
        )
        mock_scorer.score.return_value = [scored_offer]

        with patch(
            "app.jobs.coordinator.Offer",
            side_effect=ValueError("invalid offer payload"),
        ):
            result = await run_scrape_job(mock_container)

    assert result["scraped_cells"] == []
    assert result["matched_users"] == []
    assert result["continued"] is False
    mock_container.offers_repo.query_by_cell.assert_not_called()
    mock_container.offers_repo.put_batch.assert_not_called()
    mock_container.cells_repo.update_last_scraped.assert_not_called()
    mock_container.matching_service.bulk_match_users.assert_not_called()


@pytest.mark.asyncio
async def test_run_scrape_job_partial_validation_failure_keeps_existing_available(
    mock_container,
):
    cell = MarketCell(
        country="ES",
        month="2027-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_container.cells_repo.scan.return_value = [cell]

    valid_raw = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-valid",
        hotel_name="Good Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2000.00"),
        price_per_person=Decimal("1000.00"),
        price_per_day=Decimal("142.86"),
        referral_url=AnyHttpUrl("https://tui.pl/ref"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-valid")),
    )
    invalid_raw = RawOffer(
        provider=ProviderName.TUI,
        external_offer_id="tui-invalid",
        hotel_name="Bad Hotel",
        location="ES/Mallorca/Palma",
        departure_airport="WAW",
        departure_date=date(2027, 7, 10),
        return_date=date(2027, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=3,
        rating=Decimal("4.0"),
        review_count=100,
        price_total=Decimal("2500.00"),
        price_per_person=Decimal("1250.00"),
        price_per_day=Decimal("178.57"),
        referral_url=AnyHttpUrl("https://tui.pl/ref2"),
        available=True,
        room_type="Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="tui-invalid")),
    )

    invalid_offer_id = compute_offer_id(invalid_raw)
    existing_offer: Offer = Offer(
        **invalid_raw.model_dump(),
        cell_id=cell.cell_id,
        offer_id=invalid_offer_id,
        share_url=HttpUrl("https://wakacje-travelis.pl/offer/dummy/dummy"),
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1815177600,
        attractiveness_score=0.5,
    )

    mock_container.tui_provider.search = AsyncMock(
        return_value=[valid_raw, invalid_raw]
    )
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    with patch("app.jobs.coordinator.get_scorer") as mock_get_scorer:
        mock_scorer = mock_get_scorer.return_value
        mock_scorer.score.return_value = [
            ScoredOffer(**valid_raw.model_dump(), attractiveness_score=0.85),
            ScoredOffer(**invalid_raw.model_dump(), attractiveness_score=0.75),
        ]

        mock_container.offers_repo.query_by_cell.return_value = [existing_offer]

        original_offer_cls = Offer

        def offer_factory(*args, **kwargs):
            external_id = kwargs.get("external_offer_id")
            if external_id == "tui-invalid":
                raise ValueError("invalid offer payload")
            return original_offer_cls(*args, **kwargs)

        with patch("app.jobs.coordinator.Offer", side_effect=offer_factory):
            await run_scrape_job(mock_container)

    saved = mock_container.offers_repo.put_batch.call_args[0][0]
    unavailable_existing = [
        o for o in saved if o.offer_id == invalid_offer_id and not o.available
    ]
    assert unavailable_existing == []


def test_is_cell_month_past():
    past_cell = MarketCell(
        country="ES",
        month="2026-07",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    current_cell = MarketCell(
        country="ES",
        month="2026-08",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    future_cell = MarketCell(
        country="ES",
        month="2026-09",
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    today = date(2026, 8, 2)

    assert is_cell_month_past(past_cell, today=today) is True
    assert is_cell_month_past(current_cell, today=today) is False
    assert is_cell_month_past(future_cell, today=today) is False


@pytest.mark.asyncio
async def test_run_scrape_job_skips_past_month_cell(mock_container):
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
    mock_container.tui_provider.search = AsyncMock(return_value=[])
    mock_container.wakacje_provider.search = AsyncMock(return_value=[])

    with patch("app.jobs.coordinator.is_cell_month_past", return_value=True):
        result = await run_scrape_job(mock_container)

    assert result["scraped_cells"] == []
    assert result["matched_users"] == []
    mock_container.tui_provider.search.assert_not_called()
    mock_container.wakacje_provider.search.assert_not_called()
    mock_container.cells_repo.update_last_scraped.assert_not_called()
