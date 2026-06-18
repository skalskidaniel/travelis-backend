from datetime import date
from calendar import monthrange

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

_http_url_adapter = TypeAdapter(AnyHttpUrl)


def parse_optional_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return str(_http_url_adapter.validate_python(raw))
    except ValidationError:
        return None


def month_date_bounds(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-", maxsplit=1)
    year = int(year_str)
    month_number = int(month_str)
    last_day = monthrange(year, month_number)[1]
    return date(year, month_number, 1), date(year, month_number, last_day)
