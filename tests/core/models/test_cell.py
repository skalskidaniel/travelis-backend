from pydantic import ValidationError
import pytest

from core.models.cell import MarketCell
from core.models.offer import BoardType


def test_market_cell_accepts_country_from_registry():
    cell = MarketCell(
        cell_id="1234567890abcdef",
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )
    assert cell.country == "MX"


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
