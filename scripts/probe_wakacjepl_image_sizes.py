#!/usr/bin/env python3
"""Probe whether Wakacje.pl search `imageSizes` affects returned image dimensions.

Fetches one offer (pinned by hotelId) and repeats search with several requested
image sizes. Reports photo dict keys, URL path dimensions, and actual pixel
size when the image bytes can be parsed.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import struct
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.models.cell import MarketCell  # noqa: E402
from core.models.offer import BoardType  # noqa: E402
from core.providers.utils import month_date_bounds  # noqa: E402
from core.providers.wakacjepl.main import (  # noqa: E402
    SEARCH_URL,
    WakacjePlProvider,
)
from core.providers.wakacjepl.utils import parse_wakacje_image_url  # noqa: E402

DEFAULT_IMAGE_SIZES = [
    "570,428",
    "800,600",
    "1024,768",
    "1140,856",
    "1200,900",
    "1280,960",
    "1600,1200",
    "1920,1080",
    "2048,1536",
]

URL_DIMENSIONS_RE = re.compile(r"-(\d+)-(\d+)\.(?:jpe?g|webp|png)(?:\?|$)", re.I)
PHOTO_KEY_RE = re.compile(r"^(\d+),(\d+)$")


def _next_month_yyyy_mm() -> str:
    from datetime import date

    today = date.today()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return f"{year}-{month:02d}"


def _parse_requested_size(value: str) -> tuple[int, int] | None:
    match = PHOTO_KEY_RE.match(value.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_url_dimensions(url: str) -> tuple[int, int] | None:
    match = URL_DIMENSIONS_RE.search(url)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_photo_keys(photos: object) -> list[str]:
    if not isinstance(photos, dict):
        return []
    return [str(key) for key in photos]


def _read_image_pixel_size(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                return None
            marker = data[offset + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = struct.unpack(">H", data[offset + 5 : offset + 7])[0]
                width = struct.unpack(">H", data[offset + 7 : offset + 9])[0]
                return width, height
            if marker in {0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9}:
                offset += 2
                continue
            if marker in {0xDA, 0xD9}:
                return None
            segment_length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
            offset += 2 + segment_length
        return None

    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk_header = data[12:16]
        if chunk_header == b"VP8 ":
            width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return width, height
        if chunk_header == b"VP8L":
            bits = struct.unpack("<I", data[21:25])[0]
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
        if chunk_header == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height

    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width = struct.unpack(">I", data[16:20])[0]
        height = struct.unpack(">I", data[20:24])[0]
        return width, height

    return None


async def _fetch_pixel_size(
    client: httpx.AsyncClient,
    url: str,
    *,
    referer: str,
) -> tuple[tuple[int, int] | None, int | None]:
    try:
        response = await client.get(
            url,
            follow_redirects=True,
            headers={"referer": referer},
        )
    except httpx.HTTPError:
        return None, None
    if response.status_code != 200 or not response.content:
        return None, response.status_code
    return _read_image_pixel_size(response.content), response.status_code


@dataclass(slots=True)
class SizeProbeResult:
    requested: str
    requested_w: int
    requested_h: int
    http_status: int | None
    offer_found: bool
    photo_keys: list[str]
    image_url: str | None
    key_dimensions: tuple[int, int] | None
    url_dimensions: tuple[int, int] | None
    pixel_dimensions: tuple[int, int] | None
    matches_requested: bool
    notes: str

    def as_row(self) -> dict[str, Any]:
        def fmt_dims(dims: tuple[int, int] | None) -> str:
            if dims is None:
                return "-"
            return f"{dims[0]}x{dims[1]}"

        return {
            "requested": self.requested,
            "http": self.http_status,
            "found": self.offer_found,
            "photo_keys": ",".join(self.photo_keys) or "-",
            "key_dims": fmt_dims(self.key_dimensions),
            "url_dims": fmt_dims(self.url_dimensions),
            "pixel_dims": fmt_dims(self.pixel_dimensions),
            "matches": self.matches_requested,
            "notes": self.notes,
            "image_url": self.image_url or "-",
        }


def _build_search_payload(
    provider: WakacjePlProvider,
    cell: MarketCell,
    *,
    image_sizes: list[str],
    hotel_id: int | None,
) -> list[dict[str, Any]]:
    departure_from, departure_to = month_date_bounds(cell.month)
    country_id = int(provider._country_ids[cell.country])  # noqa: SLF001
    service_id = int(provider._service_values[cell.board.value])  # noqa: SLF001
    payload = provider._build_search_payload(  # noqa: SLF001
        cell=cell,
        page=1,
        country_id=country_id,
        service_id=service_id,
        departure_from=departure_from,
        departure_to=departure_to,
    )
    mutated = deepcopy(payload)
    params = mutated[0]["params"]
    params["imageSizes"] = image_sizes
    params["limit"] = 50
    params["hotelId"] = [hotel_id] if hotel_id is not None else []
    return mutated


async def _search_offer(
    client: httpx.AsyncClient,
    provider: WakacjePlProvider,
    cell: MarketCell,
    *,
    image_sizes: list[str],
    hotel_id: int | None,
    target_offer_id: str | None = None,
) -> tuple[dict[str, Any] | None, int | None]:
    payload = _build_search_payload(
        provider,
        cell,
        image_sizes=image_sizes,
        hotel_id=hotel_id,
    )
    try:
        response = await client.post(
            SEARCH_URL,
            json=payload,
            headers=provider._search_headers(),  # noqa: SLF001
        )
    except httpx.HTTPError:
        return None, None

    if response.status_code != 200:
        return None, response.status_code

    body = response.json()
    offers = body.get("data", {}).get("offers", [])
    if not isinstance(offers, list):
        return None, response.status_code

    if target_offer_id is not None:
        for item in offers:
            if str(item.get("offerId")) == target_offer_id:
                return item, response.status_code
    if offers:
        return offers[0], response.status_code
    return None, response.status_code


def _analyze_offer(
    *,
    requested: str,
    offer: dict[str, Any] | None,
    http_status: int | None,
    target_offer_id: str,
    pixel_dimensions: tuple[int, int] | None,
) -> SizeProbeResult:
    requested_dims = _parse_requested_size(requested)
    if requested_dims is None:
        raise ValueError(f"Invalid requested size format: {requested!r}")
    requested_w, requested_h = requested_dims

    if offer is None:
        return SizeProbeResult(
            requested=requested,
            requested_w=requested_w,
            requested_h=requested_h,
            http_status=http_status,
            offer_found=False,
            photo_keys=[],
            image_url=None,
            key_dimensions=None,
            url_dimensions=None,
            pixel_dimensions=None,
            matches_requested=False,
            notes="offer not found in search response",
        )

    same_offer = str(offer.get("offerId")) == target_offer_id
    photos = offer.get("photos")
    photo_keys = _parse_photo_keys(photos)
    image_url = parse_wakacje_image_url(photos)

    key_dimensions: tuple[int, int] | None = None
    if photo_keys:
        key_dimensions = _parse_requested_size(photo_keys[0])

    url_dimensions = _parse_url_dimensions(image_url) if image_url else None

    matches = False
    notes: list[str] = []
    if not same_offer:
        notes.append(f"fallback offer {offer.get('offerId')}")
    if key_dimensions == (requested_w, requested_h):
        matches = True
        notes.append("photo key matches requested size")
    elif key_dimensions is not None:
        notes.append(f"photo key is {key_dimensions[0]}x{key_dimensions[1]}")
    else:
        notes.append("no parseable photo key")

    if url_dimensions == (requested_w, requested_h):
        matches = True
        notes.append("URL path matches requested size")
    elif url_dimensions is not None:
        notes.append(f"URL path is {url_dimensions[0]}x{url_dimensions[1]}")
    elif image_url:
        notes.append("URL has no WxH suffix")

    if pixel_dimensions == (requested_w, requested_h):
        matches = True
        notes.append("downloaded pixels match requested size")
    elif pixel_dimensions is not None:
        notes.append(f"downloaded pixels are {pixel_dimensions[0]}x{pixel_dimensions[1]}")

    return SizeProbeResult(
        requested=requested,
        requested_w=requested_w,
        requested_h=requested_h,
        http_status=http_status,
        offer_found=same_offer,
        photo_keys=photo_keys,
        image_url=image_url,
        key_dimensions=key_dimensions,
        url_dimensions=url_dimensions,
        pixel_dimensions=pixel_dimensions,
        matches_requested=matches,
        notes="; ".join(notes),
    )


def _print_table(rows: list[dict[str, Any]], *, show_pixels: bool) -> None:
    columns: list[tuple[str, int]] = [
        ("requested", 12),
        ("http", 4),
        ("found", 5),
        ("photo_keys", 14),
        ("key_dims", 10),
        ("url_dims", 10),
    ]
    if show_pixels:
        columns.append(("pixel_dims", 10))
    columns.append(("matches", 7))
    header = " ".join(name.ljust(width) for name, width in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            " ".join(
                str(row[col]).ljust(width)[:width] for col, width in columns
            )
        )


async def run_probe(args: argparse.Namespace) -> int:
    timeout = httpx.Timeout(args.timeout_seconds)
    cell = MarketCell(
        country=args.country,
        month=args.month,
        min_stars=args.min_stars,
        board=BoardType(args.board),
        adults=args.adults,
        children=args.children,
        activation_count=1,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        provider = WakacjePlProvider(client=client)

        baseline_size = args.sizes[0]
        print(f"Fetching baseline offer with imageSizes=[{baseline_size!r}] ...")
        baseline_offer, baseline_status = await _search_offer(
            client,
            provider,
            cell,
            image_sizes=[baseline_size],
            hotel_id=None,
        )
        if baseline_offer is None:
            print(
                f"Baseline search failed (HTTP {baseline_status}). "
                "Cannot continue without an offer."
            )
            return 1

        hotel_id = int(baseline_offer["hotelId"])
        target_offer_id = str(baseline_offer["offerId"])
        hotel_name = baseline_offer.get("hotelName") or baseline_offer.get("name") or "?"

        print(
            f"Pinned offer {target_offer_id} ({hotel_name}) via hotelId={hotel_id}\n"
        )

        results: list[SizeProbeResult] = []
        for requested in args.sizes:
            offer, http_status = await _search_offer(
                client,
                provider,
                cell,
                image_sizes=[requested],
                hotel_id=hotel_id,
                target_offer_id=target_offer_id,
            )
            image_url = (
                parse_wakacje_image_url(offer.get("photos")) if offer else None
            )
            pixel_dims = None
            if args.fetch_pixels and image_url:
                pixel_dims, fetch_status = await _fetch_pixel_size(
                    client,
                    image_url,
                    referer="https://www.wakacje.pl/",
                )
                if pixel_dims is None and fetch_status is not None:
                    result_notes_extra = f"image fetch HTTP {fetch_status}"
                else:
                    result_notes_extra = ""
            else:
                result_notes_extra = ""

            result = _analyze_offer(
                requested=requested,
                offer=offer,
                http_status=http_status,
                target_offer_id=target_offer_id,
                pixel_dimensions=pixel_dims,
            )
            if result_notes_extra:
                result.notes = f"{result.notes}; {result_notes_extra}" if result.notes else result_notes_extra
            results.append(result)
            if args.delay_seconds:
                await asyncio.sleep(args.delay_seconds)

    rows = [result.as_row() for result in results]
    _print_table(rows, show_pixels=args.fetch_pixels)

    matching = [r for r in results if r.matches_requested]
    distinct_keys = sorted({",".join(r.photo_keys) or "-" for r in results})
    distinct_url_dims = sorted(
        {
            f"{r.url_dimensions[0]}x{r.url_dimensions[1]}"
            if r.url_dimensions
            else "-"
            for r in results
        }
    )
    distinct_pixel_dims = sorted(
        {
            f"{r.pixel_dimensions[0]}x{r.pixel_dimensions[1]}"
            if r.pixel_dimensions
            else "-"
            for r in results
        }
    )

    print()
    print("Summary")
    print(f"- Tested sizes: {len(results)}")
    print(f"- Distinct photo keys returned: {distinct_keys}")
    print(f"- Distinct URL path dimensions: {distinct_url_dims}")
    if args.fetch_pixels:
        print(f"- Distinct downloaded pixel sizes: {distinct_pixel_dims}")
    print(f"- Sizes that matched requested dimensions: {len(matching)}/{len(results)}")

    if len(distinct_keys) == 1 and len(matching) <= 1:
        print(
            "\nConclusion: imageSizes appears IGNORED — all requests returned the "
            "same photo key/dimensions regardless of requested size."
        )
        return 2

    if matching:
        matched_sizes = ", ".join(r.requested for r in matching)
        print(
            f"\nConclusion: imageSizes affects response for at least: {matched_sizes}"
        )
        return 0

    print(
        "\nConclusion: responses varied but none clearly matched requested sizes. "
        "Inspect the table and image URLs above."
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Wakacje.pl search imageSizes values against one pinned offer."
    )
    parser.add_argument("--country", default="GR", help="ISO country code for search.")
    parser.add_argument(
        "--month",
        default=_next_month_yyyy_mm(),
        help="Search month in YYYY-MM format (default: next month).",
    )
    parser.add_argument("--min-stars", type=int, default=4)
    parser.add_argument(
        "--board",
        default="all-inclusive",
        choices=[b.value for b in BoardType],
    )
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.2,
        help="Sleep between size probes to reduce rate limiting.",
    )
    parser.add_argument(
        "--fetch-pixels",
        action="store_true",
        help=(
            "Download image URLs to verify actual pixel dimensions "
            "(often blocked/404 without browser session)."
        ),
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        default=DEFAULT_IMAGE_SIZES,
        help="Requested imageSizes values as 'width,height' strings.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(run_probe(args)))


if __name__ == "__main__":
    main()
