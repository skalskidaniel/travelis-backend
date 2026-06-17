from datetime import date
from core.models.common import BoardType

REPRESENTATIVE_CHILD_AGE_YEARS = 8

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
