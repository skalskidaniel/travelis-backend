import hashlib

from pydantic import ValidationError
import pytest

from core.models.cell import MarketCell
from core.models.common import BoardType


def test_market_cell_accepts_country_from_registry():
    cell = MarketCell(
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    assert cell.country == "MX"
    raw_key = "MX:2026-07:4:all-inclusive:2:0"
    expected_cell_id = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    assert cell.cell_id == expected_cell_id


def test_market_cell_rejects_country_not_in_registry():
    with pytest.raises(ValidationError, match="Unsupported country code 'XX'"):
        MarketCell(
            cell_id="1234567890abcdef",
            country="XX",
            month="2026-07",
            min_stars=4,
            board=BoardType.ALL_INCLUSIVE,
            adults=2,
            children=0,
            activation_count=1,
        )


def test_market_cell_rejects_mismatched_explicit_cell_id():
    with pytest.raises(
        ValidationError, match="cell_id must match deterministic hash of cell dimensions"
    ):
        MarketCell(
            cell_id="1234567890abcdef",
            country="MX",
            month="2026-07",
            min_stars=4,
            board=BoardType.ALL_INCLUSIVE,
            adults=2,
            children=0,
            activation_count=1,
        )
