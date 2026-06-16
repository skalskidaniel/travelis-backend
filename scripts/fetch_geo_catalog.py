#!/usr/bin/env python3
"""Download provider geo catalogs for TraveLis (wakacje.pl + TUI)."""

from __future__ import annotations

import argparse
import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS_DIR = ROOT / "docs/providers"

WAKACJE_BASE_URL = "https://www.wakacje.pl/v2/api"
WAKACJE_FILTERS_PATH = PROVIDERS_DIR / "wakacjepl/wakacjepl_filters.json"
WAKACJE_OUTPUT = PROVIDERS_DIR / "wakacjepl/wakacjepl_geo_catalog.json"

TUI_GS_INITIAL_URL = "https://www.tui.pl/api/services/tui-search/api/gs/initial"
TUI_FILTERS_PATH = PROVIDERS_DIR / "tui/tui_filters.json"
TUI_OUTPUT = PROVIDERS_DIR / "tui/tui_geo_catalog.json"

WAKACJE_HEADERS = {"User-Agent": "Mozilla/5.0", "accept": "application/json"}

TUI_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "tui-api-key": "www",
    "x-market": "pl",
    "x-market-language": "pl",
    "x-market-currency": "PLN",
    "accept": "application/json",
    "content-type": "application/json",
    "origin": "https://www.tui.pl",
}

WAKACJE_DEPARTURE_LABELS: dict[str, str] = {
    "BER": "Berlin",
    "BZG": "Bydgoszcz",
    "DRS": "Drezno",
    "GDN": "Gdańsk",
    "KTW": "Katowice",
    "KRK": "Kraków",
    "LUZ": "Lublin",
    "LCJ": "Łódź",
    "SZY": "Szczytno",
    "OSR": "Ostrawa",
    "POZ": "Poznań",
    "RZE": "Rzeszów",
    "SZZ": "Szczecin",
    "WMI": "Warszawa - Modlin",
    "WAW": "Warszawa - Chopin",
    "WRO": "Wrocław",
    "RDO": "Warszawa - Radom",
    "IEG": "Zielona Góra",
}

WAKACJE_DEPARTURE_SLUGS: dict[str, str] = {
    "BER": "z-berlina",
    "BZG": "z-bydgoszczy",
    "GDN": "z-gdanska",
    "KTW": "z-katowic",
    "KRK": "z-krakowa",
    "LUZ": "z-lublina",
    "LCJ": "z-lodzi",
    "POZ": "z-poznania",
    "RZE": "z-rzeszowa",
    "SZZ": "z-szczecina",
    "WMI": "z-warszawy-modlin",
    "WAW": "z-warszawy-chopin",
    "WRO": "z-wroclawia",
    "RDO": "z-radomia",
    "IEG": "z-zielonej-gory",
}

WAKACJE_DEPARTURE_SAMPLE_OFFER_IDS = (745287, 1058607, 1094045, 916232, 843652)

TUI_GS_INITIAL_BODY = {
    "pageUrl": "/wypoczynek",
    "tripType": "WS",
    "adultsCount": 2,
    "sortCode": "price",
    "selectedAirports": [],
    "selectedDestinationsCodes": [],
    "selectedFilterValues": {},
    "durationFrom": 6,
    "durationTo": 8,
    "seasonStartDate": "2023-02-28T23:00:00.000Z",
    "startDate": None,
    "endDate": None,
    "fullPrice": False,
    "disableOtherDirections": False,
    "multiroomEnabled": True,
    "hasAdditionalOptions": True,
    "promotedOffersEndpointEnabled": False,
    "childrenBirthDates": [],
}


def _slugify_departure(label: str) -> str:
    normalized = unicodedata.normalize("NFD", label.lower())
    ascii_text = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    slug = ascii_text.replace(" - ", "-").replace(" ", "-")
    return f"z-{slug}"


def _write_catalog(path: Path, catalog: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {path} ({path.stat().st_size / 1024:.1f} KB)")


def _fetch_wakacje(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    response = client.get(
        f"{WAKACJE_BASE_URL}/{path}", headers=WAKACJE_HEADERS, timeout=60
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success", True):
        raise RuntimeError(f"wakacje API error for {path}: {body}")
    return body["data"]


def _load_wakacje_departure_airports(client: httpx.Client) -> dict[str, dict[str, str]]:
    filters = json.loads(WAKACJE_FILTERS_PATH.read_text(encoding="utf-8"))
    iata_to_id: dict[str, str] = filters["departure"]

    labels_by_id: dict[str, str] = {}
    for offer_id in WAKACJE_DEPARTURE_SAMPLE_OFFER_IDS:
        response = client.post(
            f"{WAKACJE_BASE_URL}/offerConfiguratorV2/filters",
            json={
                "offerId": offer_id,
                "departureDate": [],
                "duration": [],
                "adults": 2,
                "kidsAges": [],
                "service": [],
                "transportType": [],
                "departurePlace": [],
                "providerIds": [],
                "isConfiguratorToFilterEnabled": True,
            },
            headers={**WAKACJE_HEADERS, "content-type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        for place in response.json()["data"]["departurePlaces"]:
            labels_by_id[str(place["value"])] = place["label"]
        time.sleep(0.05)

    departure_airports: dict[str, dict[str, str]] = {}
    for iata, departure_id in sorted(iata_to_id.items(), key=lambda item: item[1]):
        name = labels_by_id.get(departure_id) or WAKACJE_DEPARTURE_LABELS.get(iata)
        if not name:
            continue
        departure_airports[departure_id] = {
            "iata": iata,
            "name": name,
            "slug": WAKACJE_DEPARTURE_SLUGS.get(iata, _slugify_departure(name)),
        }

    generic_warsaw = labels_by_id.get("278")
    if generic_warsaw:
        departure_airports["278"] = {
            "iata": "WAW",
            "name": generic_warsaw,
            "slug": "z-warszawy",
        }

    return departure_airports


def build_wakacje_catalog(client: httpx.Client) -> dict[str, Any]:
    countries = _fetch_wakacje(client, "geoCatalogCountries")

    catalog: dict[str, Any] = {
        "provider": "wakacje.pl",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "countries": f"{WAKACJE_BASE_URL}/geoCatalogCountries",
            "regions_and_cities": f"{WAKACJE_BASE_URL}/geoCatalogRegionsAndCities/{{countryId}}",
            "departure_airports": f"{WAKACJE_BASE_URL}/offerConfiguratorV2/filters",
        },
        "countries": {},
        "regions": {},
        "cities": {},
        "departure_airports": _load_wakacje_departure_airports(client),
    }

    for country in countries:
        country_id = str(country["value"])
        iso_code = country.get("code")
        if iso_code:
            catalog["countries"][country_id] = {
                "iso": iso_code,
                "name": country.get("label"),
            }

        try:
            regions = _fetch_wakacje(client, f"geoCatalogRegionsAndCities/{country_id}")
        except Exception:
            regions = []

        for region in regions:
            region_id = str(region["value"])
            catalog["regions"][region_id] = {
                "country_id": country_id,
                "name": region.get("label"),
            }

            for city in region.get("children", []):
                city_id = str(city["value"])
                catalog["cities"][city_id] = {
                    "country_id": country_id,
                    "region_id": region_id,
                    "name": city.get("label"),
                }

        time.sleep(0.05)

    catalog["stats"] = {
        "country_count": len(catalog["countries"]),
        "region_count": len(catalog["regions"]),
        "city_count": len(catalog["cities"]),
        "departure_airport_count": len(catalog["departure_airports"]),
    }
    return catalog


def _tui_destination_iso_map() -> dict[str, str]:
    filters = json.loads(TUI_FILTERS_PATH.read_text(encoding="utf-8"))
    destination_to_iso: dict[str, str] = {}

    for iso_code, destination_codes in filters["destinationsCodes"].items():
        if iso_code == "any":
            continue
        for destination_code in destination_codes:
            destination_to_iso[destination_code] = iso_code
        if iso_code not in {"ES-CN", "PT-20", "PT-30"}:
            destination_to_iso[iso_code] = iso_code

    return destination_to_iso


def build_tui_catalog(client: httpx.Client) -> dict[str, Any]:
    response = client.post(
        TUI_GS_INITIAL_URL, headers=TUI_HEADERS, json=TUI_GS_INITIAL_BODY, timeout=60
    )
    response.raise_for_status()
    filters = response.json()["filters"]

    region_filter = next(item for item in filters if item.get("filterType") == "REGION")
    airport_filter = next(
        item for item in filters if item.get("filterType") == "AIRPORT"
    )
    destination_to_iso = _tui_destination_iso_map()

    catalog: dict[str, Any] = {
        "provider": "tui.pl",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "destinations_and_departures": TUI_GS_INITIAL_URL,
        },
        "countries": {},
        "regions": {},
        "departure_airports": {},
    }

    for country_node in region_filter["options"]:
        country_code = country_node["code"]
        country_name = country_node.get("label")
        country_iso = destination_to_iso.get(country_code, country_code)

        catalog["countries"][country_code] = {
            "iso": country_iso,
            "name": country_name,
        }

        child_regions = country_node.get("options") or []
        if child_regions:
            for region_node in child_regions:
                region_code = region_node["code"]
                catalog["regions"][region_code] = {
                    "country_code": country_code,
                    "name": region_node.get("label"),
                }
        else:
            catalog["regions"][country_code] = {
                "country_code": country_code,
                "name": country_name,
            }

    for airport in airport_filter["options"]:
        code = airport["code"]
        catalog["departure_airports"][code] = {
            "code": code,
            "name": airport.get("label"),
        }

    catalog["stats"] = {
        "country_count": len(catalog["countries"]),
        "region_count": len(catalog["regions"]),
        "departure_airport_count": len(catalog["departure_airports"]),
    }
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch provider geo catalogs.")
    parser.add_argument(
        "--provider",
        choices=("wakacje", "tui", "all"),
        default="all",
        help="Which provider catalog to refresh (default: all).",
    )
    args = parser.parse_args()

    with httpx.Client() as client:
        if args.provider in {"wakacje", "all"}:
            wakacje_catalog = build_wakacje_catalog(client)
            _write_catalog(WAKACJE_OUTPUT, wakacje_catalog)
            print("wakacje stats:", wakacje_catalog["stats"])

        if args.provider in {"tui", "all"}:
            tui_catalog = build_tui_catalog(client)
            _write_catalog(TUI_OUTPUT, tui_catalog)
            print("tui stats:", tui_catalog["stats"])


if __name__ == "__main__":
    main()
