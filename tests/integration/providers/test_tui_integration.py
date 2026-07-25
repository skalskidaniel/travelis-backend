import pytest
import pytest_asyncio
import httpx
from datetime import date, datetime, timezone
import os
import re
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar
from decimal import Decimal
from pydantic import AnyHttpUrl, HttpUrl

from core.exceptions.provider import ProviderTimeoutException, TooManyRequestsException
from core.models.cell import MarketCell
from core.models.offer import (
    BoardType,
    RawOffer,
    ProviderName,
    Offer,
    OfferMetadata,
    TuiMetadata,
)
from core.providers.tui.main import (
    TuiProvider,
)
from core.providers.resources import tui_filters

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


_TUI_FILTERS = tui_filters
SUPPORTED_COUNTRY_CODES = tuple(
    sorted(
        code
        for code in _TUI_FILTERS["destinationsCodes"].keys()
        if re.fullmatch(r"[A-Z]{2}", code)
    )
)
SUPPORTED_BOARD_TYPES = tuple(
    BoardType(board_value) for board_value in _TUI_FILTERS["board"].keys()
)
SUPPORTED_MIN_STARS = tuple(
    sorted(
        int(stars_value)
        for stars_value in _TUI_FILTERS["minHotelCategory"].keys()
        if stars_value.isdigit()
    )
)


def _max_concurrent_live_requests() -> int:
    raw_value = os.environ.get("TUI_TEST_CONCURRENCY")
    if raw_value is None:
        return 5
    try:
        parsed = int(raw_value)
    except ValueError:
        return 5
    return max(1, parsed)


MAX_CONCURRENT_LIVE_REQUESTS = _max_concurrent_live_requests()
MAX_RETRY_ATTEMPTS = max(1, int(os.environ.get("PROVIDER_TEST_RETRY_ATTEMPTS", "2")))
RETRY_BASE_DELAY_SECONDS = float(os.environ.get("PROVIDER_TEST_RETRY_DELAY", "1.0"))
T = TypeVar("T")


def _next_month_bucket() -> str:
    today = date.today()
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return next_month.strftime("%Y-%m")


async def _run_with_transient_retry(call: Callable[[], Awaitable[T]]) -> T:
    # noinspection DuplicatedCode
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            return await call()
        except (ProviderTimeoutException, TooManyRequestsException):
            if attempt == MAX_RETRY_ATTEMPTS:
                raise
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)

    msg = "Retry loop exited unexpectedly."
    raise RuntimeError(msg)


@pytest_asyncio.fixture()
async def live_provider() -> AsyncIterator[TuiProvider]:
    limits = httpx.Limits(
        max_connections=MAX_CONCURRENT_LIVE_REQUESTS,
        max_keepalive_connections=MAX_CONCURRENT_LIVE_REQUESTS,
    )
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as live_client:
        yield TuiProvider(client=live_client)


@pytest.mark.asyncio
async def test_search_filters_consistency():
    cell = MarketCell(
        country="EG",
        month=_next_month_bucket(),
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=1,
        activation_count=1,
    )

    async with httpx.AsyncClient(timeout=30.0) as live_client:
        live_provider = TuiProvider(client=live_client)
        offers: list[RawOffer] = await _run_with_transient_retry(
            lambda: live_provider.search(cell)
        )

    assert offers, (
        "Live TUI search returned no offers for the configured next-month cell."
    )

    for o in offers:
        assert isinstance(o, RawOffer)
        assert o.provider == ProviderName.TUI
        assert o.location.startswith("Egipt/")
        assert o.departure_date.strftime("%Y-%m") == cell.month
        assert o.stars >= 3
        assert o.board == BoardType.ALL_INCLUSIVE


@pytest.mark.asyncio
async def test_search_country_consistency(
    live_provider: TuiProvider,
):
    month_bucket = _next_month_bucket()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LIVE_REQUESTS)
    failures: list[str] = []

    async def _check_country(country_code: str) -> None:
        async with semaphore:
            cell = MarketCell(
                country=country_code,
                month=month_bucket,
                min_stars=3,
                board=BoardType.HALF_BOARD,
                adults=2,
                children=0,
                activation_count=1,
            )
            offers: list[RawOffer] = await _run_with_transient_retry(
                lambda: live_provider.search(cell)
            )

        if not offers:
            return

        top_level_country_labels = {
            offer.location.split("/", maxsplit=1)[0] for offer in offers
        }
        if not top_level_country_labels:
            failures.append(
                f"country={country_code}: no top-level country labels found"
            )
            return
        if any(not country_label for country_label in top_level_country_labels):
            failures.append(f"country={country_code}: empty top-level country label")
            return

        if len(top_level_country_labels) == 1:
            return
        else:
            failures.append(
                f"country={country_code}: unexpected mixed country labels {sorted(top_level_country_labels)}"
            )

    await asyncio.gather(
        *(_check_country(country_code) for country_code in SUPPORTED_COUNTRY_CODES)
    )
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.asyncio
async def test_search_board_consistency(
    live_provider: TuiProvider,
):
    month_bucket = _next_month_bucket()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LIVE_REQUESTS)
    failures: list[str] = []

    async def _check_board(board_type: BoardType) -> None:
        async with semaphore:
            cell = MarketCell(
                country="GR",
                month=month_bucket,
                min_stars=3,
                board=board_type,
                adults=2,
                children=0,
                activation_count=1,
            )
            offers: list[RawOffer] = await _run_with_transient_retry(
                lambda: live_provider.search(cell)
            )

        if not offers:
            return

        if not all(offer.board == board_type for offer in offers):
            failures.append(
                f"board={board_type.value}: found offers with non-matching board type"
            )

    await asyncio.gather(
        *(_check_board(board_type) for board_type in SUPPORTED_BOARD_TYPES)
    )
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.asyncio
async def test_hotel_standard_consistency(live_provider: TuiProvider):
    month_bucket = _next_month_bucket()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LIVE_REQUESTS)
    failures: list[str] = []

    async def _check_min_stars(min_stars: int) -> None:
        async with semaphore:
            cell = MarketCell(
                country="GR",
                month=month_bucket,
                min_stars=min_stars,
                board=BoardType.HALF_BOARD,
                adults=2,
                children=0,
                activation_count=1,
            )
            offers: list[RawOffer] = await _run_with_transient_retry(
                lambda: live_provider.search(cell)
            )

        if not offers:
            return

        if not all(offer.stars >= min_stars for offer in offers):
            failures.append(
                f"min_stars={min_stars}: found offers below requested hotel standard"
            )

    await asyncio.gather(
        *(_check_min_stars(min_stars) for min_stars in SUPPORTED_MIN_STARS)
    )
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.asyncio
async def test_check_availability_returns_unavailable(live_provider):
    offer: Offer = Offer(
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
        price_per_person=Decimal("1500.00"),
        price_per_day=Decimal("1500.00"),
        referral_url=AnyHttpUrl("https://www.tui.pl/wypoczynek/wlochy/dolny-adriatyk/hotel-kent-rmi17050/OfferCodeWS/KRKRMI20260622113520260622202606272210L05RMI17050DZX1AA02ROADZX1A02FCMM"),
        available=True,
        room_type="Standard Room",
        adults=2,
        children=0,
        metadata=OfferMetadata(
            tui=TuiMetadata(
                offer_code="KRKRMI20260622113520260622202606272210L05RMI17050DZX1AA02ROADZX1A02FCMM"
            ),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url=HttpUrl("https://wakacje-travelis.pl/offer/123"),
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1782086400,
    )
    available = await live_provider.check_availability(offer)
    assert available is False


@pytest.mark.asyncio
async def test_search_currency_is_pln(live_provider):
    cell = MarketCell(
        country="EG",
        month=_next_month_bucket(),
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    destination_codes = live_provider._destination_codes.get(cell.country)
    board_codes = live_provider._board_codes_for_cell(cell)
    min_hotel_category = live_provider._min_hotel_category_values.get(
        str(cell.min_stars)
    )

    payload = live_provider._build_search_payload(
        cell=cell,
        page=0,
        destination_codes=destination_codes,
        board_codes=board_codes,
        min_hotel_category=min_hotel_category,
    )

    response = await live_provider._client.post(
        "https://www.tui.pl/api/services/tui-search/api/search/offers",
        json=payload,
        headers=live_provider._search_headers(),
    )
    response.raise_for_status()
    data = response.json()

    offers = data.get("offers") or []
    if not offers:
        pytest.skip("No live offers returned to check currency.")

    for item in offers:
        assert item.get("currency") == "PLN", (
            f"Expected currency PLN, got {item.get('currency')}"
        )


@pytest.mark.asyncio
async def test_search_departure_date_bounds(live_provider: TuiProvider):
    month_bucket = _next_month_bucket()
    cell = MarketCell(
        country="EG",
        month=month_bucket,
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    offers: list[RawOffer] = await _run_with_transient_retry(
        lambda: live_provider.search(cell)
    )
    if not offers:
        pytest.skip(f"No live offers returned for TUI next-month cell {month_bucket}.")

    for offer in offers:
        assert offer.departure_date.strftime("%Y-%m") == cell.month, (
            f"Offer {offer.external_offer_id} departure date {offer.departure_date} "
            f"falls outside requested month {cell.month}"
        )


@pytest.mark.parametrize("board", list(BoardType))
@pytest.mark.asyncio
async def test_referral_url_matches_offer_page(
    live_provider: TuiProvider,
    board: BoardType,
):
    cell = MarketCell(
        country="EG",
        month=_next_month_bucket(),
        min_stars=3,
        board=board,
        adults=2,
        children=0,
        activation_count=1,
    )
    offers: list[RawOffer] = await _run_with_transient_retry(
        lambda: live_provider.search(cell)
    )
    if not offers:
        pytest.skip(
            f"Live TUI search returned no offers for next-month cell with board {board.value}."
        )

    from tests.unit.core.providers.utils import (
        PAGE_FETCH_HEADERS,
        verify_tui_offer_urls,
        offer_url_check_sample_size,
    )

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers=PAGE_FETCH_HEADERS,
    ) as page_client:
        failures = await verify_tui_offer_urls(page_client, offers)

    sample_size = offer_url_check_sample_size()
    # noinspection DuplicatedCode
    for offer in offers[:sample_size]:
        try:
            price = await live_provider.check_price(offer)
            if price <= 0:
                failures.append(
                    f"offer={offer.external_offer_id}: check_price returned non-positive price {price}"
                )
            else:
                diff_pct = abs(price - offer.price_total) / offer.price_total
                if diff_pct > 0.10:
                    failures.append(
                        f"offer={offer.external_offer_id}: price mismatch: "
                        f"check_price={price}, search price={offer.price_total} "
                        f"(diff={diff_pct:.2%})"
                    )
        except Exception as error:
            failures.append(
                f"offer={offer.external_offer_id}: check_price failed: {error}"
            )

    if failures:
        pytest.fail("\n".join(failures))
