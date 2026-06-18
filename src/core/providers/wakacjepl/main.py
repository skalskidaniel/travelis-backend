from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

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
from core.models.offer import (
    Offer,
    OfferMetadata,
    ProviderName,
    RawOffer,
    WakacjePlMetadata,
)
from core.providers.resources import wakacjepl_filters
from core.providers.utils import month_date_bounds
from core.providers.wakacjepl.utils import (
    SERVICE_TO_BOARD,
    build_wakacje_offer_page_path,
    build_wakacje_offer_selector,
    format_wakacje_date,
    parse_wakacje_image_url,
    representative_child_birthday,
)

SEARCH_URL = "https://www.wakacje.pl/v2/api/offers"
CALCULATOR_URL = "https://www.wakacje.pl/v2/api/getCalculatorOfferVariants/{offer_id}"
AVAILABILITY_URL = "https://www.wakacje.pl/v2/api/checkOfferAvailability"
WAKACJE_ORIGIN = "https://www.wakacje.pl"
PAGE_SIZE = 500
MIN_DURATION_NIGHTS = 2
MAX_DURATION_NIGHTS = 28
SUPPORTED_MIN_STARS = frozenset(range(2, 6))


class WakacjePlProvider:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._country_ids = wakacjepl_filters["countryId"]
        self._departure_places_map = wakacjepl_filters["departurePlaces"]
        self._service_values = wakacjepl_filters["service"]

    @property
    def provider(self) -> ProviderName:
        return ProviderName.WAKACJE_PL

    async def search(self, cell: MarketCell) -> list[RawOffer]:
        """Search Wakacje.pl for offers matching the given market cell.

        Validates search parameters, iterates through all paginated search results
        up to the provider's limits, and maps the provider's JSON response format
        into our unified `RawOffer` model.
        """
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

        country_id_str = self._country_ids.get(cell.country)
        if not country_id_str:
            raise CountryNotFoundException(
                f"Country code '{cell.country}' is not supported by Wakacje.pl provider."
            )
        country_id = int(country_id_str)

        service_str = self._service_values.get(cell.board.value)
        if service_str is None:
            raise BoardTypeNotSupportedException(
                f"Board type '{cell.board}' is not supported by Wakacje.pl provider."
            )
        service_id = int(service_str)

        if cell.min_stars not in SUPPORTED_MIN_STARS:
            raise MinStarsNotSupportedException(
                f"Min stars '{cell.min_stars}' is not supported by Wakacje.pl provider."
            )

        raw_offers: list[RawOffer] = []
        page = 1
        has_more = True

        while has_more and page < 30:
            payload = self._build_search_payload(
                cell=cell,
                page=page,
                country_id=country_id,
                service_id=service_id,
                departure_from=departure_from,
                departure_to=departure_to,
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
                body = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                raise ProviderAPIException(
                    f"Wakacje.pl search API returned invalid JSON: {e}"
                ) from e
            if not isinstance(body, dict):
                raise ProviderAPIException(
                    f"unexpected Wakacje.pl search response shape: expected dict, got {type(body).__name__}"
                )
            if body.get("success") is False:
                self._raise_api_response_exception("search", body)

            data = body.get("data") or {} if isinstance(body.get("data"), dict) else {}
            offers_list = data.get("offers") or []

            for item in offers_list:
                try:
                    mapped = self._map_search_offer(item, cell=cell)
                except ValidationError:
                    continue
                if mapped is not None:
                    raw_offers.append(mapped)

            if len(offers_list) < PAGE_SIZE:
                has_more = False
            else:
                page += 1

        return raw_offers

    async def check_availability(self, offer: Offer) -> bool:
        """Return whether a persisted offer is still bookable on Wakacje.pl.

        Uses a two-step process: first, calling the calculator variants API to
        retrieve a fresh offerHash, and then hitting the hotel-cards availability
        API to confirm whether it is bookable.
        """
        live_variant = await self._resolve_live_variant(offer)
        if live_variant is None:
            return False

        offer_hash, provider_code = live_variant
        status_data = await self._fetch_live_availability(
            offer, offer_hash, provider_code
        )

        return (
            status_data.get("availability") is True
            and status_data.get("status") == "OK"
        )

    async def check_price(self, offer: Offer) -> Decimal:
        """Fetch the current live price for the given offer on Wakacje.pl.

        Similar to `check_availability`, this executes the full two-step booking
        flow check to retrieve the most up-to-date total price for the offer.
        """
        live_variant = await self._resolve_live_variant(offer)
        if live_variant is None:
            return offer.price_total

        offer_hash, provider_code = live_variant
        status_data = await self._fetch_live_availability(
            offer, offer_hash, provider_code
        )

        price = status_data.get("price")
        if price is not None:
            return Decimal(str(price))

        return offer.price_total

    def _build_search_payload(
        self,
        *,
        cell: MarketCell,
        page: int,
        country_id: int,
        service_id: int,
        departure_from: date,
        departure_to: date,
    ) -> list[dict[str, Any]]:
        child_birthday = representative_child_birthday()
        children_birthdays = [child_birthday] * cell.children
        extended_arrival_date = departure_to + timedelta(days=MAX_DURATION_NIGHTS)

        return [
            {
                "method": "search.tripsSearch",
                "params": {
                    "brand": "WAK",
                    "limit": PAGE_SIZE,
                    "priceHistory": 1,
                    "imageSizes": ["570,428"],
                    "flatArray": True,
                    "multiSearch": True,
                    "withHotelRate": 1,
                    "withPromoOffer": 0,
                    "recommendationVersion": "noTUI",
                    "imageLimit": 1,
                    "withPromotionsInfo": False,
                    "type": "tours",
                    "firstMinuteTui": False,
                    "countryId": [country_id],
                    "regionId": [],
                    "cityId": [],
                    "hotelId": [],
                    "roundTripId": [],
                    "cruiseId": [],
                    "searchType": "wczasy",
                    "offersAttributes": [],
                    "alternative": {"countryId": [], "regionId": [], "cityId": []},
                    "qsVersion": "cx_v2_auction",
                    "query": {
                        "campTypes": [],
                        "qsVersion": "cx_v2_auction",
                        "qsVersionLast": 0,
                        "tab": False,
                        "candy": False,
                        "pok": None,
                        "flush": False,
                        "tourOpAndCode": None,
                        "obj_type": None,
                        "catalog": None,
                        "roomType": None,
                        "test": None,
                        "year": None,
                        "month": None,
                        "rangeDate": None,
                        "withoutLast": 0,
                        "category": False,
                        "not-attribute": False,
                        "pageNumber": page,
                        "departureDate": format_wakacje_date(departure_from),
                        "arrivalDate": format_wakacje_date(extended_arrival_date),
                        "departure": None,
                        "type": [],
                        "duration": {
                            "min": MIN_DURATION_NIGHTS,
                            "max": MAX_DURATION_NIGHTS,
                        },
                        "minPrice": None,
                        "maxPrice": None,
                        "service": [service_id],
                        "firstminute": None,
                        "attribute": [],
                        "promotion": [],
                        "tourId": None,
                        "search": None,
                        "minCategory": cell.min_stars * 10,
                        "maxCategory": 50,
                        "sort": 13,
                        "order": 1,
                        "rooms": [
                            {
                                "adult": cell.adults,
                                "kid": cell.children,
                                "ages": children_birthdays,
                            }
                        ],
                    },
                },
            }
        ]

    def _search_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": WAKACJE_ORIGIN,
            "referer": f"{WAKACJE_ORIGIN}/wczasy/?src=fromSearch",
        }

    @staticmethod
    def _metadata_for_offer(offer: Offer) -> WakacjePlMetadata:
        meta = offer.metadata.wakacje_pl
        if meta is None:
            msg = "metadata.wakacje_pl is required for Wakacje.pl availability checks"
            raise InvalidOfferMetadataException(msg)
        return meta

    async def _resolve_live_variant(self, offer: Offer) -> tuple[str, str] | None:
        variants = await self._fetch_calculator_variants(offer)
        if not variants:
            return None

        variant = variants[0]
        offer_hash = variant.get("id")
        if not offer_hash:
            return None

        meta = self._metadata_for_offer(offer)
        provider_code = variant.get("providerCode") or meta.tour_op_code or "WAK"
        return str(offer_hash), str(provider_code)

    async def _fetch_calculator_variants(self, offer: Offer) -> list[dict[str, Any]]:
        """Fetch variant details for a specific offer from the calculator API.

        This step is necessary because the search response doesn't provide the full
        `offerHash` needed for the final availability check.
        """
        meta = self._metadata_for_offer(offer)

        child_birthday = representative_child_birthday()
        children_birthdays = [child_birthday] * meta.children

        payload = {
            "adults": meta.adults,
            "kids": meta.children,
            "infants": 0,
            "kidsAges": children_birthdays,
            "serviceId": meta.service_id,
            "duration": offer.duration,
            "departureDate": format_wakacje_date(offer.departure_date),
            "transportId": meta.transport_id,
            "departureCityId": meta.departure_city_id,
            "departureCityCode": offer.departure_airport,
            "hotelId": meta.hotel_id,
            "tourId": meta.tour_operator_id,
            "cruiseId": 0,
            "roundTripId": 0,
            "isAlternativeRoom": False,
            "isOffer77": False,
        }
        if meta.tour_op_code:
            payload["tourOp"] = meta.tour_op_code

        url = CALCULATOR_URL.format(offer_id=offer.external_offer_id)

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": WAKACJE_ORIGIN,
            "referer": f"{WAKACJE_ORIGIN}{meta.offer_page_path}",
        }

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            self._raise_request_exception("calculator", e)

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderAPIException(
                f"Wakacje.pl calculator API returned invalid JSON: {e}"
            ) from e
        if not isinstance(data, dict):
            msg = f"unexpected Wakacje.pl calculator response shape: expected dict, got {type(data).__name__}"
            raise ProviderAPIException(msg)

        if data.get("success") is False:
            self._raise_api_response_exception("calculator", data)

        return (data.get("data") or {}).get("offers") or []

    async def _fetch_live_availability(
        self, offer: Offer, offer_hash: str, provider_code: str
    ) -> dict[str, Any]:
        """Check live booking availability using the final offerHash.

        This calls the `checkOfferAvailability` endpoint with a complex
        customHeaders structure and detailed participant mapping to simulate
        a booking verification.
        """
        meta = self._metadata_for_offer(offer)

        custom_headers = json.dumps(
            {
                "Page-Source": "PO",
                "Tour-Operator-Code": provider_code,
                "Tour-Operator-Id": str(meta.tour_operator_id),
                "Object-Id": str(meta.hotel_id),
            }
        )

        headers = {
            "accept": "application/json",
            "referer": f"{WAKACJE_ORIGIN}{meta.offer_page_path}",
            "customHeaders": custom_headers,
        }

        params = {
            "providerCode": provider_code,
            "offerHash": offer_hash,
            "offerType": "tour",
            "includeTfgService": "true",
            "isAlternativeRoom": "false",
            "cityId": meta.city_id,
            "countryId": meta.country_id,
            "regionId": meta.region_id,
        }

        for i in range(meta.adults):
            params[f"participantsObject[participants][{i}][birthDate]"] = "1988-01-01"
            params[f"participantsObject[participants][{i}][type]"] = "adult"
            params[f"participantsObject[participants][{i}][userAllocateId]"] = i + 1

        idx = meta.adults
        child_birthday_fmt = representative_child_birthday()
        child_iso = f"{child_birthday_fmt[:4]}-{child_birthday_fmt[4:6]}-{child_birthday_fmt[6:]}"

        for i in range(meta.children):
            params[f"participantsObject[participants][{idx}][birthDate]"] = child_iso
            params[f"participantsObject[participants][{idx}][type]"] = "child"
            params[f"participantsObject[participants][{idx}][userAllocateId]"] = idx + 1
            idx += 1

        try:
            response = await self._client.get(
                AVAILABILITY_URL, params=params, headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            self._raise_request_exception("availability", e)

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ProviderAPIException(
                f"Wakacje.pl availability API returned invalid JSON: {e}"
            ) from e
        if not isinstance(data, dict):
            msg = f"unexpected Wakacje.pl availability response shape: expected dict, got {type(data).__name__}"
            raise ProviderAPIException(msg)

        if data.get("success") is False:
            self._raise_api_response_exception("availability", data)

        return data.get("data") or {}

    @staticmethod
    def _status_code_from_error(payload: dict[str, Any]) -> int | None:
        error_info = payload.get("error")
        status_value: Any = None
        if isinstance(error_info, dict):
            status_value = error_info.get("status")
        if status_value is None:
            status_value = payload.get("status") or payload.get("statusCode")

        if isinstance(status_value, int):
            return status_value
        if isinstance(status_value, str) and status_value.isdigit():
            return int(status_value)
        return None

    def _raise_api_response_exception(
        self, api_name: str, payload: dict[str, Any]
    ) -> None:
        error_info = payload.get("error")
        error_msg = "unknown error"
        if isinstance(error_info, dict) and error_info.get("message"):
            error_msg = str(error_info["message"])
        elif payload.get("msg"):
            error_msg = str(payload["msg"])

        status_code = self._status_code_from_error(payload)
        if status_code == 429:
            raise TooManyRequestsException(
                f"Wakacje.pl {api_name} API failed with status {status_code}: {error_msg}"
            )
        if status_code in {408, 504}:
            raise ProviderTimeoutException(
                f"Wakacje.pl {api_name} API failed with status {status_code}: {error_msg}"
            )

        status_label = status_code if status_code is not None else "unknown status"
        raise ProviderAPIException(
            f"Wakacje.pl {api_name} API failed with status {status_label}: {error_msg}"
        )

    @staticmethod
    def _raise_request_exception(api_name: str, error: httpx.HTTPError) -> None:
        error_msg = str(error) or error.__class__.__name__
        if isinstance(error, httpx.TimeoutException):
            raise ProviderTimeoutException(
                f"Wakacje.pl {api_name} API request failed: {error_msg}"
            ) from error

        status_code = None
        if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
            status_code = error.response.status_code
        if status_code == 429:
            raise TooManyRequestsException(
                f"Wakacje.pl {api_name} API request failed with status 429: {error_msg}"
            ) from error

        raise ProviderAPIException(
            f"Wakacje.pl {api_name} API request failed: {error_msg}"
        ) from error

    def _map_search_offer(
        self, item: dict[str, Any], *, cell: MarketCell
    ) -> RawOffer | None:
        """Map a single Wakacje.pl response dictionary into a RawOffer model.

        Returns None if critical mapping fields are missing or unsupported.
        """
        offer_id = item.get("offerId")
        name = item.get("name")
        place = item.get("place") or {}
        departure_place = item.get("departurePlace")
        departure_date_raw = item.get("departureDate")
        return_date_raw = item.get("returnDate")
        duration_nights = item.get("durationNights")
        service = item.get("service")
        category = item.get("category")
        rating_value = item.get("ratingValue")
        review_count = item.get("ratingReservationCount")
        price = item.get("price")
        room_type = item.get("roomType")
        url_name = item.get("urlName")
        hotel_id = item.get("hotelId")
        tour_operator_id = item.get("tourOperator")
        transport_id = item.get("departureType", 1)

        if not all(
            [
                offer_id is not None,
                name,
                place,
                departure_place,
                departure_date_raw,
                return_date_raw,
                duration_nights is not None,
                service is not None,
                category is not None,
                rating_value is not None,
                review_count is not None,
                price is not None,
                room_type,
                url_name,
                hotel_id is not None,
                tour_operator_id is not None,
            ]
        ):
            return None

        country = place.get("country") or {}
        region = place.get("region") or {}
        city = place.get("city") or {}

        country_name = country.get("name")
        region_name = region.get("name")
        city_name = city.get("name")

        country_slug = country.get("slug")
        region_slug = region.get("slug")
        city_slug = city.get("slug")
        country_id = country.get("id")
        region_id = region.get("id")
        city_id = city.get("id")

        if not all(
            [
                country_name,
                region_name,
                city_name,
                country_slug,
                region_slug,
                city_slug,
                country_id is not None,
                region_id is not None,
                city_id is not None,
            ]
        ):
            return None

        departure_iata = item.get("departurePlaceCode")
        if not departure_iata:
            return None

        dep_meta = self._departure_places_map.get(departure_iata)
        if not dep_meta or dep_meta.get("id") is None or not dep_meta.get("slug"):
            return None

        try:
            service_id = int(service)
            hotel_id_int = int(hotel_id)
            tour_operator_id_int = int(tour_operator_id)
            country_id_int = int(country_id)
            region_id_int = int(region_id)
            city_id_int = int(city_id)
            departure_city_id = int(dep_meta["id"])
            transport_id_int = int(transport_id)
            departure_date = datetime.strptime(departure_date_raw, "%Y-%m-%d").date()
            return_date = datetime.strptime(return_date_raw, "%Y-%m-%d").date()
            duration = int(duration_nights)
            stars = int(category) // 10 if int(category) >= 10 else int(category)
        except (TypeError, ValueError):
            return None

        # Filter out offers whose departure date falls outside the target cell's month
        departure_from, departure_to = month_date_bounds(cell.month)
        if not (departure_from <= departure_date <= departure_to):
            return None

        # Wakacje.pl sometimes return offers from different countries, it must be sorted out below
        expected_country_id_str = self._country_ids.get(cell.country)
        if expected_country_id_str and country_id_int != int(expected_country_id_str):
            return None

        if duration < 1:
            return None

        board = SERVICE_TO_BOARD.get(service_id)
        if board is None:
            return None

        rating = (Decimal(str(rating_value)) / Decimal("2")).quantize(Decimal("0.1"))

        participants = cell.adults + cell.children
        price_total = Decimal(str(price))
        price_per_day_one_person = (price_total / duration / participants).quantize(
            Decimal("0.01")
        )

        country_label = str(country_name).replace("/", " - ")
        region_label = str(region_name).replace("/", " - ")
        city_label = str(city_name).replace("/", " - ")
        location = f"{country_label}/{region_label}/{city_label}"

        offer_page_path = build_wakacje_offer_page_path(
            country_slug=country_slug,
            region_slug=region_slug,
            city_slug=city_slug,
            url_name=url_name,
            offer_id=offer_id,
        )
        offer_selector = build_wakacje_offer_selector(
            departure_date=departure_date,
            duration_nights=duration,
            board=board,
            departure_slug=dep_meta["slug"],
            adults=cell.adults,
            children=cell.children,
        )
        referral_url = f"{WAKACJE_ORIGIN}{offer_page_path}?{offer_selector}"
        image_url = parse_wakacje_image_url(item.get("photos"))

        wakacje_metadata = WakacjePlMetadata(
            hotel_id=hotel_id_int,
            tour_operator_id=tour_operator_id_int,
            tour_op_code=item.get("tourOpCode"),
            country_id=country_id_int,
            region_id=region_id_int,
            city_id=city_id_int,
            departure_city_id=departure_city_id,
            service_id=service_id,
            transport_id=transport_id_int,
            departure_slug=dep_meta["slug"],
            offer_page_path=offer_page_path,
            adults=cell.adults,
            children=cell.children,
        )

        return RawOffer(
            provider=ProviderName.WAKACJE_PL,
            external_offer_id=str(offer_id),
            hotel_name=name.strip(),
            location=location,
            departure_airport=departure_iata,
            departure_date=departure_date,
            return_date=return_date,
            duration=duration,
            board=board,
            stars=stars,
            rating=rating,
            review_count=int(review_count),
            price_total=price_total,
            price_per_day_one_person=price_per_day_one_person,
            referral_url=referral_url,
            image_url=image_url,
            available=True,
            room_type=str(room_type).strip(),
            adults=cell.adults,
            children=cell.children,
            metadata=OfferMetadata(
                wakacje_pl=wakacje_metadata,
            ),
        )
