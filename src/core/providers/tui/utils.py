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
