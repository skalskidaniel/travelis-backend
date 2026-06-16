#!/usr/bin/env python3
"""Generate TUI filters from the geo catalog source of truth."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "docs/providers/tui/tui_geo_catalog.json"
DEFAULT_OUTPUT_PATH = ROOT / "src/core/providers/resources/tui_filters.json"
DEFAULT_COUNTRY_REGISTRY_PATH = ROOT / "src/core/providers/resources/country_registry.json"
STRICT_ISO_PATTERN = re.compile(r"^[A-Z]{2}$")

BOARD_FILTERS: dict[str, str] = {
    "all-inclusive": "GT06-AI GT06-XX",
    "full-board": "GT06-FB GT06-FBP",
    "half-board": "GT06-HB GT06-HBP",
    "bed-and-breakfast": "GT06-BB",
    "none": "GT06-AO",
}

MIN_HOTEL_CATEGORY_FILTERS: dict[str, str] = {
    "5": "5s",
    "4": "4s",
    "3": "3s",
    "2": "2s",
    "any": "defaultHotelCategory",
}

TRIP_ADVISOR_RATING_FILTERS: dict[str, str] = {
    "4.5": "4.5t",
    "4": "4t",
    "3.5": "3.5t",
    "3": "3t",
    "any": "defaultTripAdvisorRating",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_registry_codes(path: Path) -> set[str]:
    payload = _load_json(path)
    raw_codes = payload.get("codes")
    if not isinstance(raw_codes, dict):
        raise ValueError("country registry must contain object field 'codes'")
    valid_codes: set[str] = set()
    for code in raw_codes.keys():
        if isinstance(code, str) and STRICT_ISO_PATTERN.fullmatch(code):
            valid_codes.add(code)
    if not valid_codes:
        raise ValueError("country registry must contain at least one two-letter code")
    return valid_codes


def build_destinations_codes(catalog: dict[str, Any]) -> dict[str, list[str]]:
    countries = catalog["countries"]
    regions = catalog["regions"]

    country_code_to_iso: dict[str, str] = {}
    for country_code, country_data in countries.items():
        iso = country_data.get("iso")
        if isinstance(iso, str) and STRICT_ISO_PATTERN.fullmatch(iso):
            country_code_to_iso[country_code] = iso

    destinations_by_iso: dict[str, set[str]] = {}
    for region_code, region_data in regions.items():
        country_code = region_data.get("country_code")
        if not isinstance(country_code, str):
            continue
        iso = country_code_to_iso.get(country_code)
        if iso is None:
            continue
        destinations_by_iso.setdefault(iso, set()).add(region_code)

    return {
        "any": [],
        **{
            iso: sorted(destination_codes)
            for iso, destination_codes in sorted(destinations_by_iso.items())
            if destination_codes
        },
    }


def build_filters(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "destinationsCodes": build_destinations_codes(catalog),
        "board": BOARD_FILTERS,
        "minHotelCategory": MIN_HOTEL_CATEGORY_FILTERS,
        "tripAdvisorRating": TRIP_ADVISOR_RATING_FILTERS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate tui_filters.json from tui_geo_catalog.json."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help=f"Path to TUI geo catalog (default: {DEFAULT_CATALOG_PATH}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output path for generated filters (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--country-registry",
        type=Path,
        default=DEFAULT_COUNTRY_REGISTRY_PATH,
        help=(
            "Path to canonical country registry "
            f"(default: {DEFAULT_COUNTRY_REGISTRY_PATH})."
        ),
    )
    args = parser.parse_args()

    catalog = _load_json(args.catalog)
    filters = build_filters(catalog)
    registry_codes = _load_registry_codes(args.country_registry)
    generated_codes = set(filters["destinationsCodes"]) - {"any"}
    unknown_codes = sorted(generated_codes - registry_codes)
    if unknown_codes:
        unknown_joined = ", ".join(unknown_codes)
        raise ValueError(
            f"generated destinations contain codes missing from country registry: {unknown_joined}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(filters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    iso_count = len(filters["destinationsCodes"]) - 1  # minus "any"
    print(f"Generated {args.output} with {iso_count} strict ISO destination groups.")


if __name__ == "__main__":
    main()
