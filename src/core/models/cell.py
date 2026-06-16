import re
from functools import lru_cache
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.models.offer import BoardType
from core.models.common import CellId
from core.providers.resources import country_registry

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


@lru_cache(maxsize=1)
def _allowed_country_codes() -> frozenset[str]:
    raw_codes = country_registry.get("codes")
    if not isinstance(raw_codes, dict):
        msg = "country registry must contain object field 'codes'"
        raise RuntimeError(msg)
    valid_codes = {
        code
        for code in raw_codes.keys()
        if isinstance(code, str) and COUNTRY_PATTERN.fullmatch(code)
    }
    if not valid_codes:
        msg = "country registry must contain at least one two-letter country code"
        raise RuntimeError(msg)
    return frozenset(valid_codes)


class MarketCell(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    cell_id: CellId = Field(description="Deterministic hash of the cell dimensions.")
    country: str = Field(
        pattern=COUNTRY_PATTERN,
        description="Destination country as ISO 3166-1 alpha-2.",
    )
    month: str = Field(
        pattern=MONTH_PATTERN,
        description="Travel month bucket as YYYY-MM.",
    )
    min_stars: int = Field(
        ge=2, le=5, description="Minimum hotel star rating for this cell."
    )
    board: BoardType = Field(description="Normalized board type scraped for this cell.")
    adults: int = Field(ge=1, description="Number of adults in the scrape occupancy.")
    children: int = Field(
        ge=0, description="Number of children in the scrape occupancy."
    )
    activation_count: int = Field(
        ge=1, description="Number of users requiring this cell."
    )
    last_scraped_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of the last successful scrape for this cell.",
    )

    @field_validator("country")
    @classmethod
    def validate_country_is_registered(cls, value: str) -> str:
        if value not in _allowed_country_codes():
            raise ValueError(f"Unsupported country code '{value}'")
        return value
