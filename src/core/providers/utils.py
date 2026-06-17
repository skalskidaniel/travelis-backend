from datetime import date
from calendar import monthrange


def month_date_bounds(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-", maxsplit=1)
    year = int(year_str)
    month_number = int(month_str)
    last_day = monthrange(year, month_number)[1]
    return date(year, month_number, 1), date(year, month_number, last_day)
