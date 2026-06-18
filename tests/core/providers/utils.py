"""Shared helpers for live offer referral URL consistency checks."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import TYPE_CHECKING, Any

import httpx

from core.models.common import BoardType
from core.models.offer import RawOffer
from core.providers.wakacjepl.utils import build_wakacje_occupancy_selector

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

TUI_BOARDING_TO_TYPE: dict[str, BoardType] = {
    "A": BoardType.ALL_INCLUSIVE,
    "H": BoardType.HALF_BOARD,
    "G": BoardType.BED_AND_BREAKFAST,
    "F": BoardType.FULL_BOARD,
    "O": BoardType.NONE,
}

BOARD_LABEL_PATTERNS: dict[BoardType, tuple[str, ...]] = {
    BoardType.ALL_INCLUSIVE: ("all inclusive",),
    BoardType.FULL_BOARD: ("full board", "pełne wyżywienie"),
    BoardType.HALF_BOARD: ("half board", "śniadania i obiadokolacje"),
    BoardType.BED_AND_BREAKFAST: ("bed and breakfast", "śniadania"),
    BoardType.NONE: ("bez wyżywienia", "własne"),
}

PAGE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

COOKIE_BANNER_SELECTORS = (
    "#onetrust-accept-btn-handler",
    'button:has-text("Akceptuj")',
    'button:has-text("Zgadzam")',
)


def offer_url_check_sample_size() -> int:
    raw_value = os.environ.get("OFFER_URL_CHECK_SAMPLE_SIZE", "3")
    try:
        parsed = int(raw_value)
    except ValueError:
        return 5
    return max(1, parsed)


def hotel_title_token(hotel_name: str) -> str:
    base = hotel_name.split("(", maxsplit=1)[0].strip()
    return base.split()[0].lower() if base else ""


def board_label_matches(board: BoardType, text: str) -> bool:
    normalized = text.lower()
    return any(label in normalized for label in BOARD_LABEL_PATTERNS[board])


def extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        msg = "Missing __NEXT_DATA__ script tag"
        raise ValueError(msg)
    return json.loads(match.group(1))


def parse_tui_offer_code_data(html: str) -> dict[str, Any]:
    next_data = extract_next_data(html)
    return next_data["props"]["pageProps"]["initialPageData"]["offerCodeData"]


def verify_tui_offer_page(
    *,
    offer: RawOffer,
    final_url: str,
    html: str,
) -> list[str]:
    failures: list[str] = []

    if offer.external_offer_id not in final_url:
        failures.append(
            f"offer id {offer.external_offer_id!r} not in final URL {final_url!r}"
        )

    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    title = title_match.group(1) if title_match else ""
    hotel_token = hotel_title_token(offer.hotel_name)
    if hotel_token and hotel_token not in title.lower():
        failures.append(f"hotel token {hotel_token!r} not in page title {title!r}")

    try:
        offer_code_data = parse_tui_offer_code_data(html)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"failed to parse TUI offerCodeData: {error}")
        return failures

    page_departure = str(offer_code_data.get("departureTime", ""))[:10]
    page_return = str(offer_code_data.get("returnTime", ""))[:10]
    page_airport = offer_code_data.get("airportCode")
    boarding_code = offer_code_data.get("boarding")
    page_board = TUI_BOARDING_TO_TYPE.get(str(boarding_code)) if boarding_code else None

    if page_departure != str(offer.departure_date):
        failures.append(
            f"departure date mismatch: page={page_departure!r} "
            f"search={offer.departure_date!r}"
        )
    if page_return != str(offer.return_date):
        failures.append(
            f"return date mismatch: page={page_return!r} search={offer.return_date!r}"
        )
    if page_airport != offer.departure_airport:
        failures.append(
            f"departure airport mismatch: page={page_airport!r} "
            f"search={offer.departure_airport!r}"
        )
    if page_board != offer.board:
        failures.append(
            f"board mismatch: page={boarding_code!r} ({page_board!r}) "
            f"search={offer.board.value!r}"
        )

    return failures


async def fetch_and_verify_tui_offer_url(
    client: httpx.AsyncClient,
    offer: RawOffer,
) -> list[str]:
    response = await client.get(str(offer.referral_url), headers=PAGE_FETCH_HEADERS)
    response.raise_for_status()
    return verify_tui_offer_page(
        offer=offer,
        final_url=str(response.url),
        html=response.text,
    )


def departure_city_label(
    departure_airport: str,
    departure_places_map: dict[str, dict[str, Any]],
) -> str:
    meta = departure_places_map.get(departure_airport) or {}
    name = str(meta.get("name") or "").strip()
    if not name:
        return departure_airport
    return name.split(" - ", maxsplit=1)[0].strip()


def format_polish_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def departure_slug_token(departure_slug: str) -> str:
    return departure_slug.removeprefix("z-").replace("-", " ")


def verify_wakacje_referral_url(offer: RawOffer) -> list[str]:
    failures: list[str] = []
    url = str(offer.referral_url)
    meta = offer.metadata.wakacje_pl
    if meta is None:
        failures.append("missing wakacje.pl metadata")
        return failures

    if meta.offer_page_path not in url:
        failures.append(f"offer page path {meta.offer_page_path!r} not in referral URL")
    if meta.departure_slug not in url:
        failures.append(f"departure slug {meta.departure_slug!r} not in referral URL")
    if f"od-{offer.departure_date.isoformat()}" not in url:
        failures.append(
            f"departure date selector od-{offer.departure_date.isoformat()} "
            "not in referral URL"
        )
    if f"{offer.duration}-dni" not in url:
        failures.append(f"duration selector {offer.duration}-dni not in referral URL")
    if offer.board.value not in url:
        failures.append(f"board selector {offer.board.value!r} not in referral URL")
    occupancy = build_wakacje_occupancy_selector(meta.adults, meta.children)
    if occupancy not in url:
        failures.append(f"occupancy selector {occupancy!r} not in referral URL")
    return failures


def verify_wakacje_rendered_page(
    *,
    offer: RawOffer,
    final_url: str,
    page_text: str,
) -> list[str]:
    failures: list[str] = []
    normalized_text = page_text.lower()

    if offer.external_offer_id not in final_url:
        failures.append(
            f"offer id {offer.external_offer_id!r} not in final URL {final_url!r}"
        )

    hotel_token = hotel_title_token(offer.hotel_name)
    if hotel_token and hotel_token not in normalized_text:
        failures.append(f"hotel token {hotel_token!r} not found on rendered page")

    adults_label = f"{offer.adults} dorosłych"
    if adults_label.lower() not in normalized_text:
        failures.append(f"adults label {adults_label!r} not found on rendered page")

    if offer.children > 0:
        child_label = (
            f"{offer.children} dziecko"
            if offer.children == 1
            else f"{offer.children} dzieci"
        )
        if child_label.lower() not in normalized_text:
            failures.append(
                f"children label {child_label!r} not found on rendered page"
            )

    departure_label = format_polish_date(offer.departure_date)
    return_label = format_polish_date(offer.return_date)
    if departure_label.lower() not in normalized_text:
        failures.append(
            f"departure date {departure_label!r} not found on rendered page"
        )
    if return_label.lower() not in normalized_text:
        failures.append(f"return date {return_label!r} not found on rendered page")

    if not board_label_matches(offer.board, page_text):
        failures.append(f"board {offer.board.value!r} not found on rendered page")

    return failures


async def dismiss_cookie_banner(page: Page) -> None:
    for selector in COOKIE_BANNER_SELECTORS:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=3_000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue


async def wait_for_wakacje_booking_widget(page: Page, *, offer: RawOffer) -> None:
    adults_label = f"{offer.adults} dorosłych"
    departure_label = format_polish_date(offer.departure_date)
    await page.wait_for_selector(f"text={adults_label}", timeout=45_000)
    await page.wait_for_selector(f"text={departure_label}", timeout=45_000)
    await page.wait_for_timeout(1_500)


async def open_wakacje_offer_page(
    page: Page, referral_url: str, *, offer: RawOffer
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            await page.goto(
                referral_url,
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            await dismiss_cookie_banner(page)
            await wait_for_wakacje_booking_widget(page, offer=offer)
            return await page.inner_text("body")
        except Exception as error:
            last_error = error
            if attempt == 2:
                raise
            await page.wait_for_timeout(2_000)
    msg = "Failed to open wakacje offer page"
    raise RuntimeError(msg) from last_error


async def fetch_and_verify_wakacje_offer_url(
    page: Page,
    offer: RawOffer,
) -> list[str]:
    failures = verify_wakacje_referral_url(offer)
    page_text = await open_wakacje_offer_page(
        page, str(offer.referral_url), offer=offer
    )
    failures.extend(
        verify_wakacje_rendered_page(
            offer=offer,
            final_url=page.url,
            page_text=page_text,
        )
    )
    return failures


async def verify_tui_offer_urls(
    client: httpx.AsyncClient,
    offers: list[RawOffer],
    *,
    sample_size: int | None = None,
) -> list[str]:
    size = sample_size if sample_size is not None else offer_url_check_sample_size()
    failures: list[str] = []
    for offer in offers[:size]:
        try:
            offer_failures = await fetch_and_verify_tui_offer_url(client, offer)
        except httpx.HTTPError as error:
            offer_failures = [f"HTTP error: {error}"]
        if offer_failures:
            prefix = (
                f"offer={offer.external_offer_id} "
                f"hotel={offer.hotel_name!r} url={offer.referral_url!r}"
            )
            failures.extend(f"{prefix}: {failure}" for failure in offer_failures)
    return failures


async def verify_wakacje_offer_urls(
    browser: Browser,
    offers: list[RawOffer],
    departure_places_map: dict[str, dict[str, Any]],
    *,
    sample_size: int | None = None,
) -> list[str]:
    _ = departure_places_map
    required_successes = (
        sample_size if sample_size is not None else offer_url_check_sample_size()
    )
    failures: list[str] = []
    successes = 0

    for offer in offers:
        if successes >= required_successes:
            break
        page = await browser.new_page(locale="pl-PL")
        try:
            try:
                offer_failures = await fetch_and_verify_wakacje_offer_url(
                    page,
                    offer,
                )
            except Exception as error:
                offer_failures = [f"Playwright error: {error}"]
            if offer_failures:
                prefix = (
                    f"offer={offer.external_offer_id} "
                    f"hotel={offer.hotel_name!r} url={offer.referral_url!r}"
                )
                failures.extend(f"{prefix}: {failure}" for failure in offer_failures)
            else:
                successes += 1
        finally:
            await page.close()

    if successes < required_successes:
        summary = (
            f"verified {successes}/{required_successes} offers "
            f"from {len(offers)} search results"
        )
        return [summary, *failures]
    return []
