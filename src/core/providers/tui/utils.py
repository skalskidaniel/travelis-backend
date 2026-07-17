from datetime import date, datetime, timezone

from core.models.common import BoardType
from core.providers.utils import parse_optional_http_url

REPRESENTATIVE_CHILD_AGE_YEARS = 8

BOARD_CODE_TO_TYPE: dict[str, BoardType] = {
    "GT06-AI": BoardType.ALL_INCLUSIVE,
    "GT06-XX": BoardType.ALL_INCLUSIVE,
    "GT06-FB": BoardType.FULL_BOARD,
    "GT06-FBP": BoardType.FULL_BOARD,
    "GT06-HB": BoardType.HALF_BOARD,
    "GT06-HBP": BoardType.HALF_BOARD,
    "GT06-BB": BoardType.BED_AND_BREAKFAST,
    "GT06-AO": BoardType.NONE,
}


def format_tui_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_tui_date(value: str) -> date:
    return datetime.strptime(value, "%d.%m.%Y").date()


def representative_child_birthday(today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    birth_year = today.year - REPRESENTATIVE_CHILD_AGE_YEARS
    return format_tui_date(date(birth_year, 1, 1))


def parse_tui_image_url(value: object) -> str | None:
    return parse_optional_http_url(value)


MAX_OFFER_IMAGES = 8


def parse_tui_image_urls(
    item: object,
    *,
    limit: int = MAX_OFFER_IMAGES,
) -> list[str]:
    if not isinstance(item, dict):
        return []

    gallery = item.get("gallery")
    if isinstance(gallery, list):
        result: list[str] = []
        for entry in gallery:
            if len(result) >= limit:
                break
            if not isinstance(entry, dict):
                continue
            if entry.get("galleryItemType") != "IMAGE":
                continue
            parsed = parse_tui_image_url(entry.get("url"))
            if parsed is not None:
                result.append(parsed)
        if result:
            return result

    fallback = parse_tui_image_url(item.get("imageUrl"))
    return [fallback] if fallback is not None else []
