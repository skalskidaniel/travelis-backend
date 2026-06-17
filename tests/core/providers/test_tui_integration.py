import pytest
import pytest_asyncio
import httpx
from datetime import date
import os
import re
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from core.exceptions.provider import ProviderTimeoutException, TooManyRequestsException
from core.models.cell import MarketCell
from core.models.offer import (
    BoardType,
    RawOffer,
    ProviderName,
)
from core.providers.tui.main import (
    TuiProvider,
)
from core.providers.resources import tui_filters


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
ALLOWED_MIXED_COUNTRY_LABEL_SETS = {
    frozenset({"Portugalia", "Hiszpania"}),
    frozenset({"Hiszpania", "Wyspy Kanaryjskie"}),
}
T = TypeVar("T")


def _next_month_bucket() -> str:
    today = date.today()
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return next_month.strftime("%Y-%m")


async def _run_with_transient_retry(call: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            return await call()
        except (ProviderTimeoutException, TooManyRequestsException):
            if attempt == MAX_RETRY_ATTEMPTS:
                raise
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)

    msg = "Retry loop exited unexpectedly."
    raise RuntimeError(msg)


@pytest_asyncio.fixture
async def live_provider() -> TuiProvider:
    limits = httpx.Limits(
        max_connections=MAX_CONCURRENT_LIVE_REQUESTS,
        max_keepalive_connections=MAX_CONCURRENT_LIVE_REQUESTS,
    )
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as live_client:
        yield TuiProvider(client=live_client)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live TUI integration tests.",
)
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
        offers = await _run_with_transient_retry(lambda: live_provider.search(cell))

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
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live TUI integration tests.",
)
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
            offers = await _run_with_transient_retry(lambda: live_provider.search(cell))

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

        labels_set = frozenset(top_level_country_labels)
        if labels_set not in ALLOWED_MIXED_COUNTRY_LABEL_SETS:
            failures.append(
                f"country={country_code}: unexpected mixed country labels {sorted(top_level_country_labels)}"
            )

    await asyncio.gather(
        *(_check_country(country_code) for country_code in SUPPORTED_COUNTRY_CODES)
    )
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live TUI integration tests.",
)
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
            offers = await _run_with_transient_retry(lambda: live_provider.search(cell))

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
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live TUI integration tests.",
)
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
            offers = await _run_with_transient_retry(lambda: live_provider.search(cell))

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
