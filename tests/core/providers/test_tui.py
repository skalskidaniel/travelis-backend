import pytest
import respx
import httpx
from decimal import Decimal
from datetime import date, datetime, timezone
from unittest.mock import patch

from core.models.cell import MarketCell
from core.models.offer import (
    BoardType,
    Offer,
    OfferMetadata,
    ProviderName,
    RawOffer,
    TuiMetadata,
)
from core.providers.tui.main import (
    TuiProvider,
    SEARCH_URL,
    AVAILABILITY_URL,
)
from core.providers.resources import country_registry, tui_filters

from core.exceptions.provider import (
    CountryNotFoundException,
    BoardTypeNotSupportedException,
    MinStarsNotSupportedException,
    PastDatesException,
    DateMismatchException,
    InvalidOfferMetadataException,
    ProviderAPIException,
)


@pytest.fixture
def async_client():
    return httpx.AsyncClient()


@pytest.fixture
def tui_provider(async_client):
    return TuiProvider(client=async_client)


def test_provider_identity(tui_provider):
    assert tui_provider.provider == ProviderName.TUI


def test_destination_codes_are_registered():
    registry_codes = set(country_registry["codes"].keys())
    destination_codes = set(tui_filters["destinationsCodes"].keys()) - {"any"}
    assert destination_codes <= registry_codes


@pytest.mark.asyncio
async def test_search_invalid_country(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch.dict(tui_provider._destination_codes, {"EG": []}):
        with pytest.raises(
            CountryNotFoundException, match="Country code 'EG' is not supported"
        ):
            await tui_provider.search(cell)


@pytest.mark.asyncio
async def test_search_unsupported_board(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.NONE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch.dict(tui_provider._board_filter_values, {BoardType.NONE.value: None}):
        with pytest.raises(
            BoardTypeNotSupportedException, match="Board type 'none' is not supported"
        ):
            await tui_provider.search(cell)


@pytest.mark.asyncio
async def test_search_unsupported_stars(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=2,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch.dict(tui_provider._min_hotel_category_values, {"2": None}):
        with pytest.raises(
            MinStarsNotSupportedException, match="Min stars '2' is not supported"
        ):
            await tui_provider.search(cell)


@pytest.mark.asyncio
async def test_search_past_dates(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2020-01",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with pytest.raises(PastDatesException, match="Both search dates are in the past"):
        await tui_provider.search(cell)


@pytest.mark.asyncio
async def test_search_date_mismatch(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch("core.providers.tui.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 7, 31), date(2026, 7, 1))
        with pytest.raises(
            DateMismatchException, match="Departure date .* is after return/end date"
        ):
            await tui_provider.search(cell)


@pytest.mark.asyncio
@respx.mock
async def test_search_api_failure(tui_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderAPIException, match="TUI search API request failed"):
        await tui_provider.search(cell)


@pytest.fixture
def tui_search_item():
    return {
        "offerCode": "TUI-OFFER-1",
        "hotelName": "Test Hotel",
        "boardCode": "GT06-AI",
        "city": "Hurghada",
        "breadcrumbs": [
            {"label": "Egipt"},
            {"label": "Hurghada"},
            {"label": "Hurghada City"},
        ],
        "departureDate": "12.07.2026",
        "returnDate": "19.07.2026",
        "offerUrl": "/wypoczynek/eg-test",
        "discountFullPrice": 5000,
        "discountPerPersonPrice": 2500,
        "hotelStandard": 4,
        "tripAdvisorRating": 4.5,
        "tripAdvisorReviewsNo": 100,
        "departureFlight": {"departure": {"airportCode": "WAW"}},
        "roomName": "Family Room Standard",
    }


@pytest.fixture
def tui_search_cell():
    return MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )


def test_map_search_offer_image_url(tui_provider, tui_search_item, tui_search_cell):
    item = {
        **tui_search_item,
        "imageUrl": "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/example.jpg?quality=80",
    }

    with patch("core.providers.tui.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 7, 1), date(2026, 7, 31))
        offer: RawOffer = tui_provider._map_search_offer(item, cell=tui_search_cell)

    assert offer is not None
    assert (
        str(offer.image_url)
        == "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/example.jpg?quality=80"
    )


@pytest.mark.parametrize("image_url", [None, "", "not-a-url"])
def test_map_search_offer_missing_or_invalid_image_url(
    tui_provider, tui_search_item, tui_search_cell, image_url
):
    item = {**tui_search_item, "imageUrl": image_url}

    with patch("core.providers.tui.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 7, 1), date(2026, 7, 31))
        offer: RawOffer = tui_provider._map_search_offer(item, cell=tui_search_cell)

    assert offer is not None
    assert offer.image_url is None


# noinspection DuplicatedCode
@pytest.fixture
def sample_offer():
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


@pytest.mark.asyncio
@respx.mock
async def test_check_availability(tui_provider, sample_offer):
    respx.get(url=AVAILABILITY_URL).mock(
        return_value=httpx.Response(200, json={"status": "OK"})
    )
    available = await tui_provider.check_availability(sample_offer)
    assert available is True
    assert respx.calls.last.request.url.params["offerCode"] == "TUI-OFFER-1"

    respx.get(url=AVAILABILITY_URL).mock(
        return_value=httpx.Response(200, json={"status": "UNAVAILABLE"})
    )
    available = await tui_provider.check_availability(sample_offer)
    assert available is False

    offer_no_tui = sample_offer.model_copy(deep=True)
    offer_no_tui.metadata.tui = None
    with pytest.raises(InvalidOfferMetadataException, match="metadata.tui is required"):
        await tui_provider.check_availability(offer_no_tui)

    respx.get(url=AVAILABILITY_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(
        ProviderAPIException, match="TUI availability API request failed"
    ):
        await tui_provider.check_availability(sample_offer)

    respx.get(url=AVAILABILITY_URL).mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(
        ProviderAPIException, match="unexpected TUI availability response shape"
    ):
        await tui_provider.check_availability(sample_offer)


@pytest.mark.asyncio
@respx.mock
async def test_check_price(tui_provider, sample_offer):
    mock_payload = {"priceInformationData": {"priceData": {"amount": 5432.10}}}
    respx.get(url=AVAILABILITY_URL).mock(
        return_value=httpx.Response(200, json=mock_payload)
    )
    price = await tui_provider.check_price(sample_offer)
    assert price == Decimal("5432.10")

    respx.get(url=AVAILABILITY_URL).mock(return_value=httpx.Response(200, json={}))
    price = await tui_provider.check_price(sample_offer)
    assert price == Decimal("5000.00")

    offer_no_tui = sample_offer.model_copy(deep=True)
    offer_no_tui.metadata.tui = None
    with pytest.raises(InvalidOfferMetadataException, match="metadata.tui is required"):
        await tui_provider.check_price(offer_no_tui)

    respx.get(url=AVAILABILITY_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(
        ProviderAPIException, match="TUI availability API request failed"
    ):
        await tui_provider.check_price(sample_offer)
