from datetime import date

import pytest

from core.models.common import BoardType
from core.providers.wakacjepl.utils import (
    build_wakacje_offer_page_path,
    build_wakacje_offer_selector,
    build_wakacje_occupancy_selector,
    parse_wakacje_image_url,
)


def test_build_wakacje_offer_page_path():
    assert (
        build_wakacje_offer_page_path(
            country_slug="hiszpania",
            region_slug="fuerteventura",
            city_slug="costa-calma",
            url_name="r2-pajara-beach",
            offer_id=442045,
        )
        == "/oferty/hiszpania/fuerteventura/costa-calma/r2-pajara-beach-442045.html"
    )


def test_build_wakacje_occupancy_selector_adults_only():
    assert build_wakacje_occupancy_selector(2, 0) == "2dorosle"


def test_build_wakacje_occupancy_selector_single_adult():
    assert build_wakacje_occupancy_selector(1, 0) == "dla-singli"


def test_build_wakacje_occupancy_selector_with_one_child():
    today = date(2026, 6, 18)
    assert (
        build_wakacje_occupancy_selector(2, 1, today=today)
        == "2dorosle-1dziecko-20180101"
    )


@pytest.mark.parametrize("children_count", [2, 3, 4, 5])
def test_build_wakacje_occupancy_selector_with_multiple_children(children_count):
    today = date(2026, 6, 18)
    expected_birthdays = "-".join(["20180101"] * children_count)
    assert (
        build_wakacje_occupancy_selector(2, children_count, today=today)
        == f"2dorosle-{children_count}dzieci-{expected_birthdays}"
    )


def test_build_wakacje_offer_selector():
    today = date(2026, 6, 18)
    assert (
        build_wakacje_offer_selector(
            departure_date=date(2026, 6, 29),
            duration_nights=7,
            board=BoardType.ALL_INCLUSIVE,
            departure_slug="z-wroclawia",
            adults=2,
            children=1,
            today=today,
        )
        == "od-2026-06-29,7-dni,all-inclusive,z-wroclawia,2dorosle-1dziecko-20180101"
    )


def test_parse_wakacje_image_url_relative_path():
    photos = {
        "570,428": ["/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg"]
    }
    assert (
        parse_wakacje_image_url(photos)
        == "https://i.wakacje.pl/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg"
    )


def test_parse_wakacje_image_url_absolute_path():
    photos = {"570,428": ["https://i.wakacje.pl/media/hotel/example.jpg"]}
    assert (
        parse_wakacje_image_url(photos)
        == "https://i.wakacje.pl/media/hotel/example.jpg"
    )


def test_parse_wakacje_image_url_picks_first():
    photos = {
        "570,428": [
            "https://i.wakacje.pl/media/hotel/first.jpg",
            "https://i.wakacje.pl/media/hotel/second.jpg",
        ]
    }
    assert (
        parse_wakacje_image_url(photos) == "https://i.wakacje.pl/media/hotel/first.jpg"
    )


@pytest.mark.parametrize(
    "photos",
    [
        None,
        {},
        {"570,428": []},
        {"570,428": [""]},
        {"570,428": ["not-a-url"]},
    ],
)
def test_parse_wakacje_image_url_returns_none_on_missing_or_invalid(photos):
    assert parse_wakacje_image_url(photos) is None
