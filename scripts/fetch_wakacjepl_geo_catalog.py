#!/usr/bin/env python3
"""Download wakacje.pl geo catalog and write a compact lookup JSON for TraveLis APIs."""

from __future__ import annotations

import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://www.wakacje.pl/v2/api"
FILTERS_PATH = Path(__file__).resolve().parents[1] / "docs/providers/wakacjepl/wakacjepl_filters.json"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "docs/providers/wakacjepl/wakacjepl_geo_catalog.json"
)
HEADERS = {"User-Agent": "Mozilla/5.0", "accept": "application/json"}

# Labels for airports in wakacjepl_filters.json not returned by offer configurator sampling.
DEPARTURE_LABELS: dict[str, str] = {
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

# Wakacje offer URL departure slugs (`od-...` selector segment).
DEPARTURE_SLUGS: dict[str, str] = {
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

# Sample offers used to discover departure labels from offerConfiguratorV2/filters.
DEPARTURE_SAMPLE_OFFER_IDS = (745287, 1058607, 1094045, 916232, 843652)


def _fetch(client: httpx.Client, path: str) -> list[dict]:
    response = client.get(f"{BASE_URL}/{path}", headers=HEADERS, timeout=60)
    response.raise_for_status()
    body = response.json()
    if not body.get("success", True):
        raise RuntimeError(f"API error for {path}: {body}")
    return body["data"]


def _slugify_departure(label: str) -> str:
    normalized = unicodedata.normalize("NFD", label.lower())
    ascii_text = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    slug = ascii_text.replace(" - ", "-").replace(" ", "-")
    return f"z-{slug}"


def _load_departure_airports(client: httpx.Client) -> dict[str, dict[str, str]]:
    filters = json.loads(FILTERS_PATH.read_text(encoding="utf-8"))
    iata_to_id: dict[str, str] = filters["departure"]
    id_to_iata = {value: iata for iata, value in iata_to_id.items()}

    labels_by_id: dict[str, str] = {}
    for offer_id in DEPARTURE_SAMPLE_OFFER_IDS:
        response = client.post(
            f"{BASE_URL}/offerConfiguratorV2/filters",
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
            headers={**HEADERS, "content-type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        for place in response.json()["data"]["departurePlaces"]:
            labels_by_id[str(place["value"])] = place["label"]
        time.sleep(0.05)

    departure_airports: dict[str, dict[str, str]] = {}
    for iata, departure_id in sorted(iata_to_id.items(), key=lambda item: item[1]):
        name = labels_by_id.get(departure_id) or DEPARTURE_LABELS.get(iata)
        if not name:
            continue
        departure_airports[departure_id] = {
            "iata": iata,
            "name": name,
            "slug": DEPARTURE_SLUGS.get(iata, _slugify_departure(name)),
        }

    # Generic Warszawa (278) appears in configurator but is not in filters.json.
    generic_warsaw = labels_by_id.get("278")
    if generic_warsaw:
        departure_airports["278"] = {
            "iata": "WAW",
            "name": generic_warsaw,
            "slug": "z-warszawy",
        }

    return departure_airports


def build_catalog(client: httpx.Client) -> dict:
    countries = _fetch(client, "geoCatalogCountries")

    catalog: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "countries": {},
        "regions": {},
        "cities": {},
        "departure_airports": _load_departure_airports(client),
    }

    for country in countries:
        country_id = str(country["value"])
        iso_code = country.get("code")
        country_name = country.get("label")
        if iso_code:
            catalog["countries"][country_id] = {
                "iso": iso_code,
                "name": country_name,
            }

        try:
            regions = _fetch(client, f"geoCatalogRegionsAndCities/{country_id}")
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

    return catalog


def main(output: Path = DEFAULT_OUTPUT) -> None:
    with httpx.Client() as client:
        catalog = build_catalog(client)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    size_kb = output.stat().st_size / 1024
    print(f"Wrote {output} ({size_kb:.1f} KB)")
    print(
        "countries=%d regions=%d cities=%d departure_airports=%d"
        % (
            len(catalog["countries"]),
            len(catalog["regions"]),
            len(catalog["cities"]),
            len(catalog["departure_airports"]),
        )
    )


if __name__ == "__main__":
    main()
