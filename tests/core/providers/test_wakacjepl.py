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
    WakacjePlMetadata,
    RawOffer,
)
from core.providers.wakacjepl.main import (
    WakacjePlProvider,
    SEARCH_URL,
    CALCULATOR_URL,
    AVAILABILITY_URL,
)

from core.exceptions.provider import (
    CountryNotFoundException,
    BoardTypeNotSupportedException,
    PastDatesException,
    DateMismatchException,
    InvalidOfferMetadataException,
    MinStarsNotSupportedException,
    ProviderAPIException,
)


@pytest.fixture
def async_client():
    return httpx.AsyncClient()


@pytest.fixture
def wakacjepl_provider(async_client):
    return WakacjePlProvider(client=async_client)


def test_provider_identity(wakacjepl_provider):
    assert wakacjepl_provider.provider == ProviderName.WAKACJE_PL


@pytest.mark.asyncio
async def test_search_invalid_country(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch.dict(wakacjepl_provider._country_ids, {}, clear=True):
        with pytest.raises(
            CountryNotFoundException, match="Country code 'EG' is not supported"
        ):
            await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
async def test_search_unsupported_board(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.NONE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch.dict(wakacjepl_provider._country_ids, {"EG": "37"}):
        with patch.dict(wakacjepl_provider._service_values, {}, clear=True):
            with pytest.raises(
                BoardTypeNotSupportedException,
                match="Board type 'none' is not supported",
            ):
                await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
async def test_search_unsupported_stars(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with (
        patch.dict(wakacjepl_provider._country_ids, {"EG": "37"}),
        patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
        patch("core.providers.wakacjepl.main.SUPPORTED_MIN_STARS", frozenset({3, 5})),
    ):
        with pytest.raises(
            MinStarsNotSupportedException, match="Min stars '4' is not supported"
        ):
            await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
async def test_search_past_dates(wakacjepl_provider):
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
        await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
async def test_search_date_mismatch(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with patch("core.providers.wakacjepl.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 7, 31), date(2026, 7, 1))
        with pytest.raises(
            DateMismatchException, match="Departure date .* is after return/end date"
        ):
            await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
@respx.mock
async def test_search_api_failure(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with (
        patch.dict(wakacjepl_provider._country_ids, {"EG": "37"}),
        patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
    ):
        respx.post(SEARCH_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(
            ProviderAPIException, match="Wakacje.pl search API request failed"
        ):
            await wakacjepl_provider.search(cell)


@pytest.mark.asyncio
@respx.mock
async def test_search_api_envelope_failure(wakacjepl_provider):
    cell = MarketCell(
        country="EG",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )
    with (
        patch.dict(wakacjepl_provider._country_ids, {"EG": "37"}),
        patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
    ):
        respx.post(SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": False,
                    "msg": "getStoreBoxOffers",
                    "error": {"message": "backend validation failed", "status": 400},
                    "data": None,
                },
            )
        )
        with pytest.raises(ProviderAPIException, match="Wakacje.pl search API failed"):
            await wakacjepl_provider.search(cell)


@pytest.fixture
def sample_wakacje_offer():
    return Offer(
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="916232",
        hotel_name="Kakkos Terra Blue",
        location="Grecja/Kreta/Ierapetra",
        departure_airport="RZE",
        departure_date=date(2026, 8, 26),
        return_date=date(2026, 9, 2),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=5,
        rating=Decimal("3.8"),  # 7.5 / 2
        review_count=40,
        price_total=Decimal("6148.00"),
        price_per_day=Decimal("439.14"),
        referral_url=(
            "https://www.wakacje.pl/oferty/grecja/kreta/ierapetra/kakkos-terra-blue-916232.html"
            "?od-2026-08-26,7-dni,all-inclusive,z-rzeszowa,2dorosle"
        ),
        available=True,
        room_type="Pokój standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(
            wakacje_pl=WakacjePlMetadata(
                hotel_id=17001,
                tour_operator_id=1588,
                tour_op_code="GRCS",
                country_id=29,
                region_id=29004,
                city_id=29011912,
                departure_city_id=1909,
                service_id=1,
                transport_id=1,
                departure_slug="z-rzeszowa",
                offer_page_path="/oferty/grecja/kreta/ierapetra/kakkos-terra-blue-916232.html",
                adults=2,
                children=0,
            ),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url="https://wakacje-travelis.pl/offer/123",
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1787702400,
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_happy_path(wakacjepl_provider):
    cell = MarketCell(
        country="GR",
        month="2026-08",
        min_stars=5,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_response = {
        "success": True,
        "data": {
            "count": 1,
            "offers": [
                {
                    "offerId": 916232,
                    "name": "Kakkos Terra Blue",
                    "place": {
                        "country": {"id": 29, "name": "Grecja", "slug": "grecja"},
                        "region": {"id": 29004, "name": "Kreta", "slug": "kreta"},
                        "city": {
                            "id": 29011912,
                            "name": "Ierapetra",
                            "slug": "ierapetra",
                        },
                    },
                    "departureDate": "2026-08-26",
                    "returnDate": "2026-09-02",
                    "durationNights": 7,
                    "departurePlace": "Rzeszów",
                    "departurePlaceCode": "RZE",
                    "service": 1,
                    "category": 50,
                    "ratingValue": 7.5,
                    "ratingReservationCount": 40,
                    "price": 6148,
                    "roomType": "Pokój standard",
                    "urlName": "kakkos-terra-blue",
                    "hotelId": 17001,
                    "tourOperator": 1588,
                    "tourOpCode": "GRCS",
                    "departureType": 1,
                    "photos": {
                        "570,428": [
                            "/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg"
                        ]
                    },
                }
            ],
        },
    }

    with patch("core.providers.wakacjepl.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 8, 1), date(2026, 8, 31))

        with (
            patch.dict(wakacjepl_provider._country_ids, {"GR": "29"}),
            patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
            patch.dict(
                wakacjepl_provider._departure_places_map,
                {"RZE": {"name": "Rzeszów", "id": 1909, "slug": "z-rzeszowa"}},
            ),
        ):
            respx.post(SEARCH_URL).mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            offers: list[RawOffer] = await wakacjepl_provider.search(cell)

            assert len(offers) == 1
            offer: RawOffer = offers[0]
            assert isinstance(offer, RawOffer)
            assert offer.rating == Decimal("3.8")
            assert offer.board == BoardType.ALL_INCLUSIVE
            assert offer.stars == 5
            assert offer.location == "Grecja/Kreta/Ierapetra"
            assert offer.price_total == Decimal("6148.00")
            assert offer.metadata.wakacje_pl.tour_op_code == "GRCS"
            assert (
                str(offer.referral_url)
                == "https://www.wakacje.pl/oferty/grecja/kreta/ierapetra/kakkos-terra-blue-916232.html"
                "?od-2026-08-26,7-dni,all-inclusive,z-rzeszowa,2dorosle"
            )
            assert (
                offer.metadata.wakacje_pl.offer_page_path
                == "/oferty/grecja/kreta/ierapetra/kakkos-terra-blue-916232.html"
            )
            assert (
                str(offer.image_url)
                == "https://www.wakacje.pl/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg"
            )


@pytest.mark.asyncio
@respx.mock
async def test_search_maps_missing_photos_to_none_image_url(wakacjepl_provider):
    cell = MarketCell(
        country="GR",
        month="2026-08",
        min_stars=5,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_response = {
        "success": True,
        "data": {
            "count": 1,
            "offers": [
                {
                    "offerId": 916232,
                    "name": "Kakkos Terra Blue",
                    "place": {
                        "country": {"id": 29, "name": "Grecja", "slug": "grecja"},
                        "region": {"id": 29004, "name": "Kreta", "slug": "kreta"},
                        "city": {
                            "id": 29011912,
                            "name": "Ierapetra",
                            "slug": "ierapetra",
                        },
                    },
                    "departureDate": "2026-08-26",
                    "returnDate": "2026-09-02",
                    "durationNights": 7,
                    "departurePlace": "Rzeszów",
                    "departurePlaceCode": "RZE",
                    "service": 1,
                    "category": 50,
                    "ratingValue": 7.5,
                    "ratingReservationCount": 40,
                    "price": 6148,
                    "roomType": "Pokój standard",
                    "urlName": "kakkos-terra-blue",
                    "hotelId": 17001,
                    "tourOperator": 1588,
                    "tourOpCode": "GRCS",
                    "departureType": 1,
                }
            ],
        },
    }

    with patch("core.providers.wakacjepl.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 8, 1), date(2026, 8, 31))

        with (
            patch.dict(wakacjepl_provider._country_ids, {"GR": "29"}),
            patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
            patch.dict(
                wakacjepl_provider._departure_places_map,
                {"RZE": {"name": "Rzeszów", "id": 1909, "slug": "z-rzeszowa"}},
            ),
        ):
            respx.post(SEARCH_URL).mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            offers: list[RawOffer] = await wakacjepl_provider.search(cell)

            assert len(offers) == 1
            assert offers[0].image_url is None


@pytest.mark.asyncio
@respx.mock
async def test_search_skips_rows_with_invalid_provider_metadata(wakacjepl_provider):
    cell = MarketCell(
        country="GR",
        month="2026-08",
        min_stars=5,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_response = {
        "success": True,
        "data": {
            "count": 1,
            "offers": [
                {
                    "offerId": 916232,
                    "name": "Kakkos Terra Blue",
                    "place": {
                        "country": {"id": 29, "name": "Grecja", "slug": "grecja"},
                        "region": {"id": 29004, "name": "Kreta", "slug": "kreta"},
                        "city": {
                            "id": 29011912,
                            "name": "Ierapetra",
                            "slug": "ierapetra",
                        },
                    },
                    "departureDate": "2026-08-26",
                    "returnDate": "2026-09-02",
                    "durationNights": 7,
                    "departurePlace": "Rzeszów",
                    "departurePlaceCode": "RZE",
                    "service": 1,
                    "category": 50,
                    "ratingValue": 7.5,
                    "ratingReservationCount": 40,
                    "price": 6148,
                    "roomType": "Pokój standard",
                    "urlName": "kakkos-terra-blue",
                    "hotelId": 0,
                    "tourOperator": 1588,
                    "tourOpCode": "GRCS",
                    "departureType": 1,
                }
            ],
        },
    }

    with patch("core.providers.wakacjepl.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 8, 1), date(2026, 8, 31))

        with (
            patch.dict(wakacjepl_provider._country_ids, {"GR": "29"}),
            patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
            patch.dict(
                wakacjepl_provider._departure_places_map,
                {"RZE": {"name": "Rzeszów", "id": 1909, "slug": "z-rzeszowa"}},
            ),
        ):
            respx.post(SEARCH_URL).mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            offers: list[RawOffer] = await wakacjepl_provider.search(cell)

            assert offers == []


@pytest.mark.asyncio
@respx.mock
async def test_check_availability(wakacjepl_provider, sample_wakacje_offer):
    calc_url = CALCULATOR_URL.format(offer_id="916232")

    respx.post(calc_url).mock(
        return_value=httpx.Response(
            200, json={"data": {"offers": [{"id": "HASH_123", "providerCode": "GRCS"}]}}
        )
    )
    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"availability": True, "status": "OK"}}
        )
    )

    available = await wakacjepl_provider.check_availability(sample_wakacje_offer)
    assert available is True
    assert respx.calls.last.request.url.params["offerHash"] == "HASH_123"

    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"availability": False, "status": "SOLD_OUT"}}
        )
    )
    available = await wakacjepl_provider.check_availability(sample_wakacje_offer)
    assert available is False

    respx.post(calc_url).mock(
        return_value=httpx.Response(200, json={"data": {"offers": []}})
    )
    available = await wakacjepl_provider.check_availability(sample_wakacje_offer)
    assert available is False

    offer_no_meta = sample_wakacje_offer.model_copy(deep=True)
    offer_no_meta.metadata.wakacje_pl = None
    with pytest.raises(
        InvalidOfferMetadataException, match="metadata.wakacje_pl is required"
    ):
        await wakacjepl_provider.check_availability(offer_no_meta)

    respx.post(calc_url).mock(
        return_value=httpx.Response(
            200, json={"data": {"offers": [{"id": "HASH_123", "providerCode": "GRCS"}]}}
        )
    )
    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "success": False,
                "msg": "checkOfferAvailability",
                "error": {"message": "provider returned error", "status": 400},
                "data": None,
            },
        )
    )
    with pytest.raises(
        ProviderAPIException, match="Wakacje.pl availability API failed"
    ):
        await wakacjepl_provider.check_availability(sample_wakacje_offer)

    # Test that success: False without an error status (e.g. sold-out variant) returns False
    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "success": False,
                "msg": "checkOfferAvailability",
                "data": None,
            },
        )
    )
    available = await wakacjepl_provider.check_availability(sample_wakacje_offer)
    assert available is False


@pytest.mark.asyncio
@respx.mock
async def test_check_price(wakacjepl_provider, sample_wakacje_offer):
    calc_url = CALCULATOR_URL.format(offer_id="916232")

    respx.post(calc_url).mock(
        return_value=httpx.Response(
            200, json={"data": {"offers": [{"id": "HASH_123", "providerCode": "GRCS"}]}}
        )
    )
    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"availability": True, "status": "OK", "price": 6500}}
        )
    )

    price = await wakacjepl_provider.check_price(sample_wakacje_offer)
    assert price == Decimal("6500")

    respx.get(AVAILABILITY_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"availability": True, "status": "OK"}}
        )
    )
    price = await wakacjepl_provider.check_price(sample_wakacje_offer)
    assert price == Decimal("6148.00")  # Fallback to original

    respx.post(calc_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "success": False,
                "msg": "getCalculatorOfferVariants",
                "error": {"message": "variant lookup failed", "status": 400},
                "data": None,
            },
        )
    )
    with pytest.raises(ProviderAPIException, match="Wakacje.pl calculator API failed"):
        await wakacjepl_provider.check_price(sample_wakacje_offer)


@pytest.mark.asyncio
@respx.mock
async def test_search_cross_month_dates(wakacjepl_provider):
    cell = MarketCell(
        country="GR",
        month="2026-08",
        min_stars=5,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    mock_response = {
        "success": True,
        "data": {
            "count": 2,
            "offers": [
                {
                    "offerId": 916232,
                    "name": "Kakkos Terra Blue (Valid)",
                    "place": {
                        "country": {"id": 29, "name": "Grecja", "slug": "grecja"},
                        "region": {"id": 29004, "name": "Kreta", "slug": "kreta"},
                        "city": {
                            "id": 29011912,
                            "name": "Ierapetra",
                            "slug": "ierapetra",
                        },
                    },
                    "departureDate": "2026-08-28",  # Within August
                    "returnDate": "2026-09-04",
                    "durationNights": 7,
                    "departurePlace": "Rzeszów",
                    "departurePlaceCode": "RZE",
                    "service": 1,
                    "category": 50,
                    "ratingValue": 7.5,
                    "ratingReservationCount": 40,
                    "price": 6148,
                    "roomType": "Pokój standard",
                    "urlName": "kakkos-terra-blue",
                    "hotelId": 17001,
                    "tourOperator": 1588,
                    "tourOpCode": "GRCS",
                    "departureType": 1,
                },
                {
                    "offerId": 916233,
                    "name": "Kakkos Terra Blue (Invalid/September Departure)",
                    "place": {
                        "country": {"id": 29, "name": "Grecja", "slug": "grecja"},
                        "region": {"id": 29004, "name": "Kreta", "slug": "kreta"},
                        "city": {
                            "id": 29011912,
                            "name": "Ierapetra",
                            "slug": "ierapetra",
                        },
                    },
                    "departureDate": "2026-09-02",  # Outside August (in September)
                    "returnDate": "2026-09-09",
                    "durationNights": 7,
                    "departurePlace": "Rzeszów",
                    "departurePlaceCode": "RZE",
                    "service": 1,
                    "category": 50,
                    "ratingValue": 7.5,
                    "ratingReservationCount": 40,
                    "price": 6248,
                    "roomType": "Pokój standard",
                    "urlName": "kakkos-terra-blue",
                    "hotelId": 17001,
                    "tourOperator": 1588,
                    "tourOpCode": "GRCS",
                    "departureType": 1,
                },
            ],
        },
    }

    with patch("core.providers.wakacjepl.main.month_date_bounds") as mock_bounds:
        mock_bounds.return_value = (date(2026, 8, 1), date(2026, 8, 31))

        with (
            patch.dict(wakacjepl_provider._country_ids, {"GR": "29"}),
            patch.dict(wakacjepl_provider._service_values, {"all-inclusive": "1"}),
            patch.dict(
                wakacjepl_provider._departure_places_map,
                {"RZE": {"name": "Rzeszów", "id": 1909, "slug": "z-rzeszowa"}},
            ),
        ):
            route = respx.post(SEARCH_URL).mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            offers: list[RawOffer] = await wakacjepl_provider.search(cell)

            # Check that query arrivalDate was extended by 28 days: August 31st + 28 days = Sept 28th
            assert route.called
            import json

            request_payload = json.loads(route.calls.last.request.content)
            arrival_date_sent = request_payload[0]["params"]["query"]["arrivalDate"]
            assert arrival_date_sent == "2026-09-28"

            # Check that only the valid August departure was kept, and the September departure was discarded
            assert len(offers) == 1
            assert offers[0].external_offer_id == "916232"
            assert offers[0].hotel_name == "Kakkos Terra Blue (Valid)"
