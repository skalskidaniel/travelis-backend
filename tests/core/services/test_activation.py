from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.exceptions.repository import ItemNotFoundException
from core.models.cell import MarketCell
from core.models.common import BoardType
from core.models.user import UserPreferences
from core.services.activation import (
    resolve_months_for_range,
    generate_required_cells,
    ActivationService,
)


def test_resolve_months_for_range():
    ref = date(2026, 6, 15)

    # Both None -> 9 months starting from reference
    months = resolve_months_for_range(None, None, ref)
    assert len(months) == 9
    assert months[0] == "2026-06"
    assert months[8] == "2027-02"

    # Specific range spanning multiple months
    months = resolve_months_for_range(date(2026, 6, 20), date(2026, 8, 5), ref)
    assert months == ["2026-06", "2026-07", "2026-08"]

    # Start date in the past should be clipped to reference date
    months = resolve_months_for_range(date(2026, 5, 1), date(2026, 7, 10), ref)
    assert months == ["2026-06", "2026-07"]

    # Date from set, date to None -> 9 months starting from date_from
    months = resolve_months_for_range(date(2026, 8, 10), None, ref)
    assert len(months) == 9
    assert months[0] == "2026-08"
    assert months[8] == "2027-04"


def test_generate_required_cells():
    prefs = UserPreferences(
        countries=["GR", "IT"],
        adults=2,
        children=[date(2018, 5, 10)],
        board=BoardType.ALL_INCLUSIVE,
        min_stars=4,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    cells = generate_required_cells(prefs, date(2026, 6, 15))
    assert len(cells) == 2

    gr_cell = [c for c in cells if c.country == "GR"][0]
    assert gr_cell.month == "2026-07"
    assert gr_cell.min_stars == 4
    assert gr_cell.board == BoardType.ALL_INCLUSIVE
    assert gr_cell.adults == 2
    assert gr_cell.children == 1


@pytest.mark.asyncio
async def test_update_cell_activations():
    cells_repo = MagicMock()
    cells_repo.increment_activations = AsyncMock(return_value={})
    cells_repo.decrement_activations = AsyncMock()
    cells_repo.put = AsyncMock()

    service = ActivationService(cells_repo)

    old_prefs = UserPreferences(
        countries=["GR"],
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )
    new_prefs = UserPreferences(
        countries=["IT"],
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    ref = date(2026, 6, 15)
    await service.update_cell_activations(new_prefs, old_prefs, ref)

    cells_repo.decrement_activations.assert_called_once()
    dec_args = cells_repo.decrement_activations.call_args[0][0]
    assert len(dec_args) == 1

    cells_repo.increment_activations.assert_called_once()
    inc_args = cells_repo.increment_activations.call_args[0][0]
    assert len(inc_args) == 1


@pytest.mark.asyncio
async def test_update_cell_activations_creates_missing_cell():
    cells_repo = MagicMock()
    cells_repo.increment_activations = AsyncMock(
        side_effect=ItemNotFoundException("missing")
    )
    cells_repo.put = AsyncMock()

    service = ActivationService(cells_repo)

    new_prefs = UserPreferences(
        countries=["GR"],
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    ref = date(2026, 6, 15)
    await service.update_cell_activations(new_prefs, None, ref)

    cells_repo.increment_activations.assert_called_once()
    cells_repo.put.assert_called_once()
    created_cell = cells_repo.put.call_args[0][0]
    assert isinstance(created_cell, MarketCell)
    assert created_cell.country == "GR"
    assert created_cell.month == "2026-07"
    assert created_cell.activation_count == 1
