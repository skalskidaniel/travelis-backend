from datetime import date

from core.models.common import BoardType
from core.providers.utils import parse_optional_http_url

REPRESENTATIVE_CHILD_AGE_YEARS = 8
WAKACJE_ORIGIN = "https://www.wakacje.pl"

SERVICE_TO_BOARD: dict[int, BoardType] = {
    1: BoardType.ALL_INCLUSIVE,
    2: BoardType.HALF_BOARD,
    3: BoardType.BED_AND_BREAKFAST,
    4: BoardType.NONE,
    6: BoardType.FULL_BOARD,
}


def format_wakacje_date(value: date) -> str:
    """YYYY-MM-DD for request dates."""
    return value.isoformat()


def representative_child_birthday(today: date | None = None) -> str:
    """Compact yyyyMMdd for an 8-year-old."""
    today = today or date.today()
    birth_year = today.year - REPRESENTATIVE_CHILD_AGE_YEARS
    return date(birth_year, 1, 1).strftime("%Y%m%d")


def build_wakacje_occupancy_selector(
    adults: int,
    children: int,
    *,
    today: date | None = None,
) -> str:
    if adults == 1 and children == 0:
        return "dla-singli"
    occupancy = f"{adults}dorosle"
    if children > 0:
        suffix = "dziecko" if children == 1 else "dzieci"
        birthday = representative_child_birthday(today)
        birthdays = "-".join([birthday] * children)
        occupancy = f"{occupancy}-{children}{suffix}-{birthdays}"
    return occupancy


def build_wakacje_offer_selector(
    *,
    departure_date: date,
    duration_nights: int,
    board: BoardType,
    departure_slug: str,
    adults: int,
    children: int,
    today: date | None = None,
) -> str:
    return ",".join(
        [
            f"od-{format_wakacje_date(departure_date)}",
            f"{duration_nights}-dni",
            board.value,
            departure_slug,
            build_wakacje_occupancy_selector(adults, children, today=today),
        ]
    )


def build_wakacje_offer_page_path(
    *,
    country_slug: str,
    region_slug: str,
    city_slug: str,
    url_name: str,
    offer_id: str | int,
) -> str:
    return (
        f"/oferty/{country_slug}/{region_slug}/{city_slug}/{url_name}-{offer_id}.html"
    )


def parse_wakacje_image_url(
    photos: object,
    *,
    origin: str = WAKACJE_ORIGIN,
) -> str | None:
    if not isinstance(photos, dict) or not photos.keys():
        return None

    urls = photos.get(list(photos.keys())[0])
    if not isinstance(urls, list) or not urls:
        return None

    first = urls[0]
    if not isinstance(first, str):
        return None

    raw = first.strip()
    if not raw:
        return None
    if raw.startswith("/"):
        raw = f"{origin}{raw}"

    return parse_optional_http_url(raw)
