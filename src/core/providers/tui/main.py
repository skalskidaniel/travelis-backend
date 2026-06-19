from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import json

import httpx
from pydantic import ValidationError

from core.exceptions.provider import (
    BoardTypeNotSupportedException,
    CountryNotFoundException,
    DateMismatchException,
    InvalidOfferMetadataException,
    MinStarsNotSupportedException,
    PastDatesException,
    ProviderAPIException,
    ProviderTimeoutException,
    TooManyRequestsException,
)
from core.models.cell import MarketCell
from core.models.offer import RawOffer, Offer, OfferMetadata, ProviderName, TuiMetadata
from core.providers.resources import country_registry, tui_filters
from core.providers.tui.utils import (
    BOARD_CODE_TO_TYPE,
    representative_child_birthday,
    format_tui_date,
    parse_tui_date,
    parse_tui_image_url,
)
from core.providers.utils import month_date_bounds

SEARCH_URL = "https://www.tui.pl/api/services/tui-search/api/search/offers"
AVAILABILITY_URL = "https://www.tui.pl/api/www/hotel-cards/offers"
TUI_ORIGIN = "https://www.tui.pl"
DEFAULT_APP_ID = "6f8e9a2b-1c3d-4e5f-9a0b-1c2d3e4f5a6b"
PAGE_SIZE = 500
MIN_DURATION_NIGHTS = 2
MAX_DURATION_NIGHTS = 28


class TuiProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        app_id: str = DEFAULT_APP_ID,
    ) -> None:
        self._client = client
        self._app_id = app_id
        self._destination_codes = tui_filters["destinationsCodes"]
        self._board_filter_values = tui_filters["board"]
        self._min_hotel_category_values = tui_filters["minHotelCategory"]
        self._departure_airport_codes = list(tui_filters["departureAirports"])

    @property
    def provider(self) -> ProviderName:
        return ProviderName.TUI

    async def search(self, cell: MarketCell) -> list[RawOffer]:
        departure_from, departure_to = month_date_bounds(cell.month)
        today = date.today()
        if departure_from > departure_to:
            raise DateMismatchException(
                f"Departure date {departure_from} is after return/end date {departure_to}"
            )
        if departure_from < today and departure_to < today:
            raise PastDatesException(
                f"Both search dates are in the past: {departure_from} to {departure_to} (today is {today})"
            )

        destination_codes = self._destination_codes.get(cell.country)
        if not destination_codes:
            raise CountryNotFoundException(
                f"Country code '{cell.country}' is not supported by TUI provider."
            )

        board_codes = self._board_codes_for_cell(cell)
        if board_codes is None:
            raise BoardTypeNotSupportedException(
                f"Board type '{cell.board}' is not supported by TUI provider."
            )

        min_hotel_category = self._min_hotel_category_values.get(str(cell.min_stars))
        if min_hotel_category is None:
            raise MinStarsNotSupportedException(
                f"Min stars '{cell.min_stars}' is not supported by TUI provider."
            )

        raw_offers: list[RawOffer] = []
        page = 0
        pages_count = 1

        while page < pages_count and page < 30:
            payload = self._build_search_payload(
                cell=cell,
                page=page,
                destination_codes=destination_codes,
                board_codes=board_codes,
                min_hotel_category=min_hotel_category,
            )
            try:
                response = await self._client.post(
                    SEARCH_URL,
                    json=payload,
                    headers=self._search_headers(),
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                self._raise_request_exception("search", e)

            try:
                # noinspection PyUnboundLocalVariable
                data = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                raise ProviderAPIException(
                    f"TUI search API returned invalid JSON: {e}"
                ) from e
            pagination = data.get("pagination") or {}
            pages_count = int(pagination.get("pagesCount") or 0)

            for item in data.get("offers") or []:
                try:
                    mapped = self._map_search_offer(item, cell=cell)
                except ValidationError:
                    continue
                if mapped is not None:
                    raw_offers.append(mapped)

            page += 1

        return raw_offers

    async def check_availability(self, offer: Offer) -> bool:
        details = await self._fetch_offer_details(offer)
        return details.get("status") == "OK"

    async def check_price(self, offer: Offer) -> Decimal:
        details = await self._fetch_offer_details(offer)
        price_data = (details.get("priceInformationData") or {}).get("priceData") or {}
        amount = price_data.get("amount")
        if amount is None:
            return offer.price_total
        return Decimal(str(amount))

    def _board_codes_for_cell(self, cell: MarketCell) -> list[str] | None:
        board_value = self._board_filter_values.get(cell.board.value)
        if board_value is None:
            return None
        return board_value.split()

    def _build_search_payload(
        self,
        *,
        cell: MarketCell,
        page: int,
        destination_codes: list[str],
        board_codes: list[str],
        min_hotel_category: str,
    ) -> dict[str, Any]:
        departure_from, departure_to = month_date_bounds(cell.month)
        child_birthday = representative_child_birthday()
        children_birthdays = [child_birthday] * cell.children

        return {
            "childrenBirthdays": children_birthdays,
            "departureDateFrom": format_tui_date(departure_from),
            "departureDateTo": format_tui_date(departure_to),
            "departuresCodes": self._departure_airport_codes,
            "destinationsCodes": destination_codes,
            "durationFrom": MIN_DURATION_NIGHTS,
            "durationTo": MAX_DURATION_NIGHTS,
            "occupancies": [
                {
                    "adultsCount": cell.adults,
                    "childrenBirthDates": children_birthdays,
                    "participantsCount": cell.adults + cell.children,
                }
            ],
            "numberOfAdults": cell.adults,
            "offerType": "BY_PLANE",
            "filters": self._default_search_filters(
                board_codes=board_codes,
                min_hotel_category=min_hotel_category,
            ),
            "metaData": {
                "page": page,
                "pageSize": PAGE_SIZE,
                "sorting": "qualifier42DESC",
            },
        }

    @staticmethod
    def _default_search_filters(
        *,
        board_codes: list[str],
        min_hotel_category: str,
    ) -> list[dict[str, Any]]:
        return [
            {"filterId": "priceSelector", "selectedValues": []},
            {"filterId": "board", "selectedValues": board_codes},
            {"filterId": "amountRange", "selectedValues": []},
            {"filterId": "minHotelCategory", "selectedValues": [min_hotel_category]},
            {"filterId": "flight_category", "selectedValues": []},
            {
                "filterId": "tripAdvisorRating",
                "selectedValues": ["defaultTripAdvisorRating"],
            },
            {"filterId": "beach_distance", "selectedValues": ["defaultBeachDistance"]},
            {"filterId": "facilities", "selectedValues": []},
            {"filterId": "WIFI", "selectedValues": []},
            {"filterId": "sport_and_wellness", "selectedValues": []},
            {"filterId": "room_type", "selectedValues": []},
            {"filterId": "room_attributes", "selectedValues": []},
            {"filterId": "hotel_chain", "selectedValues": []},
            {"filterId": "airport_distance", "selectedValues": []},
        ]

    def _search_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json;charset=UTF-8",
            "origin": TUI_ORIGIN,
            "referer": f"{TUI_ORIGIN}/",
            "tui-api-key": "www",
            "x-market": "pl",
            "x-market-language": "pl",
            "x-market-currency": "PLN",
            "x-app-id": self._app_id,
        }

    @staticmethod
    def _availability_headers() -> dict[str, str]:
        return {
            "accept": "application/json",
            "tui-api-key": "www",
            "x-market": "pl",
            "x-market-language": "pl",
            "x-market-currency": "PLN",
        }

    async def _fetch_offer_details(self, offer: Offer) -> dict[str, Any]:
        if offer.metadata.tui is None:
            msg = "metadata.tui is required for TUI availability checks"
            raise InvalidOfferMetadataException(msg)

        try:
            response = await self._client.get(
                AVAILABILITY_URL,
                params={"offerCode": offer.metadata.tui.offer_code},
                headers=self._availability_headers(),
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            self._raise_request_exception("availability", e)

        try:
            # noinspection PyUnboundLocalVariable
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderAPIException(
                f"TUI availability API returned invalid JSON: {e}"
            ) from e
        if not isinstance(payload, dict):
            msg = f"unexpected TUI availability response shape: expected dict, got {type(payload).__name__}"
            raise ProviderAPIException(msg)
        return payload

    @staticmethod
    def _raise_request_exception(api_name: str, error: httpx.HTTPError) -> None:
        error_msg = str(error) or error.__class__.__name__
        if isinstance(error, httpx.TimeoutException):
            raise ProviderTimeoutException(
                f"TUI {api_name} API request failed: {error_msg}"
            ) from error

        status_code = None
        if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
            status_code = error.response.status_code
        if status_code == 429:
            raise TooManyRequestsException(
                f"TUI {api_name} API request failed with status 429: {error_msg}"
            ) from error

        raise ProviderAPIException(
            f"TUI {api_name} API request failed: {error_msg}"
        ) from error

    @staticmethod
    def _map_search_offer(item: dict[str, Any], *, cell: MarketCell) -> RawOffer | None:
        if item.get("soldOut"):
            return None

        offer_code = item.get("offerCode")
        hotel_name = item.get("hotelName")
        board_code = item.get("boardCode")
        city = item.get("city")
        breadcrumbs = item.get("breadcrumbs") or []
        departure_date_raw = item.get("departureDate")
        return_date_raw = item.get("returnDate")
        offer_url = item.get("offerUrl")
        price_total_raw = item.get("discountFullPrice")
        price_per_person_raw = item.get("discountPerPersonPrice")
        hotel_standard = item.get("hotelStandard")
        rating_raw = item.get("tripAdvisorRating")
        review_count = item.get("tripAdvisorReviewsNo")

        if not all(
            [
                offer_code,
                hotel_name,
                board_code,
                city,
                departure_date_raw,
                return_date_raw,
                offer_url,
                price_total_raw,
                hotel_standard is not None,
                rating_raw is not None,
                review_count is not None,
            ]
        ):
            return None

        if len(breadcrumbs) < 2:
            return None

        board = BOARD_CODE_TO_TYPE.get(board_code)
        if board is None:
            return None

        departure_flight = item.get("departureFlight") or {}
        departure_airport = (departure_flight.get("departure") or {}).get("airportCode")
        if not departure_airport:
            return None

        departure_date = parse_tui_date(departure_date_raw)
        return_date = parse_tui_date(return_date_raw)

        departure_from, departure_to = month_date_bounds(cell.month)
        if not (departure_from <= departure_date <= departure_to):
            return None

        duration = (return_date - departure_date).days
        if duration < 1:
            return None

        participants = cell.adults + cell.children
        price_total = Decimal(str(price_total_raw))
        if price_per_person_raw is not None:
            price_per_day_one_person = (
                Decimal(str(price_per_person_raw)) / duration
            ).quantize(Decimal("0.01"))
        else:
            price_per_day_one_person = (price_total / duration / participants).quantize(
                Decimal("0.01")
            )

        country_label = str(breadcrumbs[0]["label"]).replace("/", " - ")
        # Tui return offers with different country, when the destination airport is in different country
        expected_country_name = country_registry.get("codes", {}).get(cell.country)
        if expected_country_name and country_label != expected_country_name:
            return None
        region_label = str(breadcrumbs[1]["label"]).replace("/", " - ")
        if len(breadcrumbs) > 2 and breadcrumbs[2].get("label"):
            city_label = str(breadcrumbs[2]["label"])
        else:
            city_label = str(city)
        city_label = city_label.replace("/", " - ")
        location = f"{country_label}/{region_label}/{city_label}"
        room_name = item.get("roomName") or item.get("roomCode")
        if not room_name:
            return None

        image_url = parse_tui_image_url(item.get("imageUrl"))

        return RawOffer(
            provider=ProviderName.TUI,
            external_offer_id=offer_code,
            hotel_name=hotel_name.strip(),
            location=location,
            departure_airport=departure_airport,
            departure_date=departure_date,
            return_date=return_date,
            duration=duration,
            board=board,
            stars=int(hotel_standard),
            rating=Decimal(str(rating_raw)),
            review_count=int(review_count),
            price_total=price_total,
            price_per_day_one_person=price_per_day_one_person,
            referral_url=f"{TUI_ORIGIN}{offer_url}",
            image_url=image_url,
            available=True,
            room_type=str(room_name).strip(),
            adults=cell.adults,
            children=cell.children,
            metadata=OfferMetadata(
                tui=TuiMetadata(offer_code=offer_code),
            ),
        )
