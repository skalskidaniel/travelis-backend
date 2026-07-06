import pytest

from core.providers.tui.utils import parse_tui_image_url


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
