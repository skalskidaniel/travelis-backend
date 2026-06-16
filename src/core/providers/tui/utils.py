from datetime import date, datetime
from calendar import monthrange

from core.models.common import BoardType

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


def _format_tui_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _parse_tui_date(value: str) -> date:
    return datetime.strptime(value, "%d.%m.%Y").date()


def _representative_child_birthday(today: date | None = None) -> str:
    today = today or date.today()
    birth_year = today.year - REPRESENTATIVE_CHILD_AGE_YEARS
    return _format_tui_date(date(birth_year, 1, 1))


def _month_date_bounds(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-", maxsplit=1)
    year = int(year_str)
    month_number = int(month_str)
    last_day = monthrange(year, month_number)[1]
    return date(year, month_number, 1), date(year, month_number, last_day)
