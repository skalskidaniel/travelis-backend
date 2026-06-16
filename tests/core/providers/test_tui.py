import pytest
import respx
import httpx
from decimal import Decimal
from datetime import date, datetime, timezone
import pandas as pd
import numpy as np
from unittest.mock import patch

from core.models.cell import MarketCell
from core.models.offer import BoardType, RawOffer, Offer, OfferMetadata, ProviderName, TuiMetadata
from core.providers.tui.main import TuiProvider, SEARCH_URL, AVAILABILITY_URL
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


def test_tui_provider_identity(tui_provider):
    assert tui_provider.provider == ProviderName.TUI


@pytest.mark.asyncio
async def test_search_invalid_country(tui_provider):
    cell = MarketCell(
        cell_id="1234567890abcdef",
        country="XX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with pytest.raises(
        CountryNotFoundException, match="Country code 'XX' is not supported"
    ):
        await tui_provider.search(cell)


@pytest.mark.asyncio
async def test_search_unsupported_board(tui_provider):
    cell = MarketCell(
        cell_id="1234567890abcdef",
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
        cell_id="1234567890abcdef",
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
        cell_id="1234567890abcdef",
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
        cell_id="1234567890abcdef",
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch("core.providers.tui.main._month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 7, 31), date(2026, 7, 1))
        with pytest.raises(
            DateMismatchException, match="Departure date .* is after return/end date"
        ):
            await tui_provider.search(cell)


@pytest.mark.asyncio
@respx.mock
async def test_search_filters_and_validation(tui_provider):
    cell = MarketCell(
        cell_id="1234567890abcdef",
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )

    mock_response = {
        "pagination": {"pagesCount": 1},
        "offers": [
            {
                "soldOut": False,
                "offerCode": "TUI-EG-MATCHING",
                "hotelName": "Albatros Palace Resort",
                "boardCode": "GT06-AI",
                "city": "Hurghada",
                "breadcrumbs": [
                    {"label": "Egipt"},
                    {"label": "Hurghada"},
                    {"label": "Hurghada City"},
                ],
                "departureDate": "12.07.2026",
                "returnDate": "19.07.2026",
                "offerUrl": "/details-eg-matching",
                "discountFullPrice": 5000,
                "discountPerPersonPrice": 2500,
                "hotelStandard": "5",
                "tripAdvisorRating": "4.5",
                "tripAdvisorReviewsNo": "300",
                "departureFlight": {"departure": {"airportCode": "WAW"}},
                "roomName": "Family Room Standard",
            },
            {
                "soldOut": True,
                "offerCode": "TUI-EG-SOLDOUT",
                "hotelName": "Sold Out Resort",
                "boardCode": "GT06-AI",
                "city": "Hurghada",
                "breadcrumbs": [{"label": "Egipt"}, {"label": "Hurghada"}],
                "departureDate": "12.07.2026",
                "returnDate": "19.07.2026",
                "offerUrl": "/details-eg-soldout",
                "discountFullPrice": 4000,
                "hotelStandard": "4",
                "tripAdvisorRating": "4.0",
                "tripAdvisorReviewsNo": "100",
                "departureFlight": {"departure": {"airportCode": "WAW"}},
                "roomName": "Double Room Standard",
            },
            {
                "soldOut": False,
                "offerCode": "TUI-EG-INVALID-FIELDS",
                "hotelName": "Broken Resort",
                "city": "Hurghada",
                "breadcrumbs": [{"label": "Egipt"}, {"label": "Hurghada"}],
                "departureDate": "12.07.2026",
                "returnDate": "19.07.2026",
                "offerUrl": "/details-eg-broken",
                "discountFullPrice": 3000,
                "hotelStandard": "4",
                "tripAdvisorRating": "4.0",
                "tripAdvisorReviewsNo": "100",
                "departureFlight": {"departure": {"airportCode": "WAW"}},
                "roomName": "Double Room Standard",
            },
            {
                "soldOut": False,
                "offerCode": "TUI-EG-MATCHING-2",
                "hotelName": "Sunrise Royal Makadi",
                "boardCode": "GT06-XX",
                "city": "Hurghada",
                "breadcrumbs": [{"label": "Egipt"}, {"label": "Hurghada"}],
                "departureDate": "20.07.2026",
                "returnDate": "27.07.2026",
                "offerUrl": "/details-eg-matching2",
                "discountFullPrice": 6000,
                "discountPerPersonPrice": 3000,
                "hotelStandard": "4",
                "tripAdvisorRating": "4.8",
                "tripAdvisorReviewsNo": "500",
                "departureFlight": {"departure": {"airportCode": "KTW"}},
                "roomName": "Standard Room Sea View",
            },
        ],
    }

    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=mock_response))

    offers = await tui_provider.search(cell)

    assert respx.calls.called
    last_request = respx.calls.last.request
    request_payload = last_request.content
    import json

    payload_data = json.loads(request_payload)

    assert payload_data["departureDateFrom"] == "01.07.2026"
    assert payload_data["departureDateTo"] == "31.07.2026"

    assert payload_data["destinationsCodes"] == ["SSH", "MUH", "RMF", "HRG"]

    assert payload_data["numberOfAdults"] == 2
    assert len(payload_data["childrenBirthdays"]) == 1
    assert payload_data["occupancies"][0]["adultsCount"] == 2
    assert payload_data["occupancies"][0]["participantsCount"] == 3

    filters = payload_data["filters"]
    board_filter = next(f for f in filters if f["filterId"] == "board")
    assert board_filter["selectedValues"] == ["GT06-AI", "GT06-XX"]
    min_stars_filter = next(f for f in filters if f["filterId"] == "minHotelCategory")
    assert min_stars_filter["selectedValues"] == ["4s"]

    assert len(offers) == 2
    for o in offers:
        assert isinstance(o, RawOffer)

    df = pd.DataFrame(
        [
            {
                "provider": o.provider,
                "location": o.location,
                "departure_date": o.departure_date,
                "board": o.board,
                "stars": o.stars,
            }
            for o in offers
        ]
    )

    df["departure_month"] = pd.to_datetime(df["departure_date"]).dt.strftime("%Y-%m")

    assert np.all(df["provider"] == ProviderName.TUI)
    assert np.all(df["location"].str.startswith("Egipt/"))
    assert np.all(df["departure_month"] == "2026-07")
    assert np.all(df["stars"] >= 4)
    assert np.all(df["board"] == BoardType.ALL_INCLUSIVE)


@pytest.mark.asyncio
@respx.mock
async def test_search_api_failure(tui_provider):
    cell = MarketCell(
        cell_id="1234567890abcdef",
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
        price_per_day_one_person=Decimal("2500.00"),
        referral_url="https://www.tui.pl/details-eg-1",
        available=True,
        room_type="Family Room Standard",
        metadata=OfferMetadata(
            tui=TuiMetadata(offer_code="TUI-OFFER-1"),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url="https://wakacje-travelis.pl/123",
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
        return_value=httpx.Response(200, json={"status": "SOLD_OUT"})
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


@pytest.mark.asyncio
async def test_check_availability_live_unavailable(tui_provider):
    offer = Offer(
        provider=ProviderName.TUI,
        external_offer_id="KRKRMI20260622113520260622202606272210L05RMI17050DZX1AA02ROADZX1A02FCMM",
        hotel_name="Hotel Kent",
        location="Włochy/Dolny Adriatyk/Rimini",
        departure_airport="KRK",
        departure_date=date(2026, 6, 22),
        return_date=date(2026, 6, 27),
        duration=5,
        board=BoardType.BED_AND_BREAKFAST,
        stars=3,
        rating=Decimal("4.0"),
        review_count=10,
        price_total=Decimal("3000.00"),
        price_per_day_one_person=Decimal("1500.00"),
        referral_url="https://www.tui.pl/wypoczynek/wlochy/dolny-adriatyk/hotel-kent-rmi17050/OfferCodeWS/KRKRMI20260622113520260622202606272210L05RMI17050DZX1AA02ROADZX1A02FCMM",
        available=True,
        room_type="Standard Room",
        metadata=OfferMetadata(
            tui=TuiMetadata(
                offer_code="KRKRMI20260622113520260622202606272210L05RMI17050DZX1AA02ROADZX1A02FCMM"
            ),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url="https://wakacje-travelis.pl/123",
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783814400,
    )
    available = await tui_provider.check_availability(offer)
    assert available is False
