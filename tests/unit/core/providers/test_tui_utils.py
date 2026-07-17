import pytest

from core.providers.tui.utils import parse_tui_image_url, parse_tui_image_urls


def test_parse_tui_image_url_valid():
    url = "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/example.jpg?quality=80"
    assert parse_tui_image_url(url) == url


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "not-a-url",
        123,
    ],
)
def test_parse_tui_image_url_returns_none_on_missing_or_invalid(value):
    assert parse_tui_image_url(value) is None


def test_parse_tui_image_urls_from_gallery():
    item = {
        "imageUrl": "https://r.cdn.redgalaxy.com/fallback.jpg",
        "gallery": [
            {
                "url": "https://r.cdn.redgalaxy.com/gallery1.jpg",
                "galleryItemType": "IMAGE",
            },
            {
                "url": "https://r.cdn.redgalaxy.com/gallery2.jpg",
                "galleryItemType": "IMAGE",
            },
            {
                "url": "https://r.cdn.redgalaxy.com/video.mp4",
                "galleryItemType": "VIDEO",
            },
        ],
    }
    assert parse_tui_image_urls(item) == [
        "https://r.cdn.redgalaxy.com/gallery1.jpg",
        "https://r.cdn.redgalaxy.com/gallery2.jpg",
    ]


def test_parse_tui_image_urls_falls_back_to_image_url():
    item = {
        "imageUrl": "https://r.cdn.redgalaxy.com/fallback.jpg",
        "gallery": [],
    }
    assert parse_tui_image_urls(item) == ["https://r.cdn.redgalaxy.com/fallback.jpg"]


def test_parse_tui_image_urls_caps_at_eight():
    item = {
        "gallery": [
            {
                "url": f"https://r.cdn.redgalaxy.com/{i}.jpg",
                "galleryItemType": "IMAGE",
            }
            for i in range(1, 11)
        ]
    }
    assert parse_tui_image_urls(item) == [
        f"https://r.cdn.redgalaxy.com/{i}.jpg" for i in range(1, 9)
    ]


@pytest.mark.parametrize(
    "item",
    [
        None,
        {},
        {"imageUrl": None, "gallery": []},
        {"imageUrl": "not-a-url", "gallery": []},
    ],
)
def test_parse_tui_image_urls_returns_empty_on_missing_or_invalid(item):
    assert parse_tui_image_urls(item) == []
