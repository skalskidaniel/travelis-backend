#!/usr/bin/env python3
"""Probe live offer referral URLs for TUI and wakacje.pl consistency."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS_PROVIDERS = ROOT / "tests" / "core" / "providers"
for path in (SRC, TESTS_PROVIDERS):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import tests.core.providers.utils as url_check  # noqa: E402

from core.models.cell import MarketCell  # noqa: E402
from core.models.offer import BoardType  # noqa: E402
from core.providers.tui.main import TuiProvider  # noqa: E402
from core.providers.wakacjepl.main import WakacjePlProvider  # noqa: E402


def _next_month_bucket() -> str:
    today = date.today()
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return next_month.strftime("%Y-%m")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("tui", "wakacje", "both"),
        default="both",
    )
    parser.add_argument("--country", default="EG")
    parser.add_argument("--sample-size", type=int, default=None)
    return parser


async def _probe_tui(country: str, sample_size: int | None) -> list[str]:
    cell = MarketCell(
        country=country,
        month=_next_month_bucket(),
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        provider = TuiProvider(client=client)
        offers = await provider.search(cell)
        if not offers:
            return [f"TUI search returned no offers for country={country}"]
        page_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=url_check.PAGE_FETCH_HEADERS,
        )
        try:
            return await url_check.verify_tui_offer_urls(
                page_client,
                offers,
                sample_size=sample_size,
            )
        finally:
            await page_client.aclose()


async def _probe_wakacje(country: str, sample_size: int | None) -> list[str]:
    cell = MarketCell(
        country=country,
        month=_next_month_bucket(),
        min_stars=3,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        provider = WakacjePlProvider(client=client)
        offers = await provider.search(cell)
        if not offers:
            return [f"Wakacje.pl search returned no offers for country={country}"]
        departure_map = provider._departure_places_map

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            return await url_check.verify_wakacje_offer_urls(
                browser,
                offers,
                departure_map,
                sample_size=sample_size,
            )
        finally:
            await browser.close()


async def _run(args: argparse.Namespace) -> int:
    failures: list[str] = []
    if args.provider in {"tui", "both"}:
        print("=== TUI ===")
        tui_failures = await _probe_tui(args.country, args.sample_size)
        if tui_failures:
            failures.extend(tui_failures)
            for failure in tui_failures:
                print("FAIL", failure)
        else:
            print("PASS")
    if args.provider in {"wakacje", "both"}:
        print("=== Wakacje.pl ===")
        wak_failures = await _probe_wakacje(args.country, args.sample_size)
        if wak_failures:
            failures.extend(wak_failures)
            for failure in wak_failures:
                print("FAIL", failure)
        else:
            print("PASS")
    return 1 if failures else 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
