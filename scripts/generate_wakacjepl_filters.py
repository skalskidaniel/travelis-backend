#!/usr/bin/env python3
"""Generate Wakacje.pl filters from the geo catalog source of truth."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.providers.resources import COUNTRY_REGISTRY_PATH  # noqa: E402

DEFAULT_CATALOG_PATH = ROOT / "docs/providers/wakacjepl/wakacjepl_geo_catalog.json"
DEFAULT_OUTPUT_PATH = ROOT / "src/core/providers/resources/wakacjepl_filters.json"
DEFAULT_COUNTRY_REGISTRY_PATH = COUNTRY_REGISTRY_PATH
STRICT_ISO_PATTERN = re.compile(r"^[A-Z]{2}$")

SERVICE_FILTERS: dict[str, str] = {
    "all-inclusive": "1",
    "half-board": "2",
    "bed-and-breakfast": "3",
    "none": "4",
    "full-board": "6",
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


def build_filters(catalog: dict[str, Any], registry_codes: set[str]) -> dict[str, Any]:
    countries = catalog.get("countries", {})
    country_id_map: dict[str, str] = {"any": ""}

    for cid, cdata in countries.items():
        iso = cdata.get("iso")
        if isinstance(iso, str) and STRICT_ISO_PATTERN.fullmatch(iso):
            # Only include countries that are supported by our internal registry
            if iso in registry_codes:
                country_id_map[iso] = cid

    departure_places = {}
    for aid, adata in catalog.get("departure_airports", {}).items():
        iata = adata.get("iata")
        if iata and isinstance(iata, str):
            departure_places[iata] = {
                "name": adata.get("name"),
                "id": int(aid),
                "slug": adata.get("slug"),
            }

    return {
        "countryId": country_id_map,
        "service": SERVICE_FILTERS,
        "departurePlaces": departure_places,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate wakacjepl_filters.json from wakacjepl_geo_catalog.json."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help=f"Path to Wakacje.pl geo catalog (default: {DEFAULT_CATALOG_PATH}).",
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
    registry_codes = _load_registry_codes(args.country_registry)

    filters = build_filters(catalog, registry_codes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(filters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    iso_count = len(filters["countryId"]) - 1  # minus "any"
    print(f"Generated {args.output} with {iso_count} strict ISO country mappings.")


if __name__ == "__main__":
    main()
