from decimal import Decimal
from typing import Annotated
from enum import StrEnum
from pydantic import Field, PlainValidator

HEX_CELL_ID = r"^[a-f0-9]{16}$"
HEX_OFFER_ID = r"^[a-f0-9]{32}$"
IATA_CODE = r"^[A-Z]{3}$"
LOCATION_PATH = r"^[^/]+/[^/]+/[^/]+$"


# noinspection PyStringConversionWithoutDunderMethod
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


CellId = Annotated[
    str,
    Field(
        pattern=HEX_CELL_ID,
        description="Deterministic hash of market-cell dimensions (first 16 hex chars of SHA-256).",
    ),
]

OfferId = Annotated[
    str,
    Field(
        pattern=HEX_OFFER_ID,
        description="Semantic fingerprint hash of trip semantics (first 32 hex chars of SHA-256).",
    ),
]

IataCode = Annotated[
    str,
    Field(
        pattern=IATA_CODE,
        description="Departure airport IATA code (uppercase).",
    ),
]

LocationPath = Annotated[
    str,
    Field(
        pattern=LOCATION_PATH,
        description="Normalized location as Country/Region/City.",
    ),
]

PricePLN = Annotated[
    Decimal,
    PlainValidator(_to_decimal),
    Field(
        ge=Decimal(0),
        decimal_places=2,
        description="Monetary amount in PLN (up to two decimal places).",
    ),
]

Rating = Annotated[
    Decimal,
    PlainValidator(_to_decimal),
    Field(
        ge=Decimal(0),
        le=Decimal(5),
        decimal_places=1,
        description="Canonical hotel rating on a 0–5 scale (one decimal place).",
    ),
]


class ProviderName(StrEnum):
    WAKACJE_PL = "wakacje_pl"
    TUI = "tui"


class BoardType(StrEnum):
    ALL_INCLUSIVE = "all-inclusive"
    FULL_BOARD = "full-board"
    HALF_BOARD = "half-board"
    BED_AND_BREAKFAST = "bed-and-breakfast"
    NONE = "none"
