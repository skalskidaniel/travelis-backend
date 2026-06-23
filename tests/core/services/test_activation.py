from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock
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
    assert len(months) == 6
    assert months[0] == "2026-06"
    assert months[5] == "2026-11"

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
        board=[BoardType.ALL_INCLUSIVE],
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


def test_generate_required_cells_multiple_boards():
    prefs = UserPreferences(
        countries=["GR"],
        adults=2,
        children=[date(2018, 5, 10)],
        board=[BoardType.ALL_INCLUSIVE, BoardType.HALF_BOARD],
        min_stars=4,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    cells = generate_required_cells(prefs, date(2026, 6, 15))
    assert len(cells) == 2

    ai_cell = [c for c in cells if c.board == BoardType.ALL_INCLUSIVE][0]
    hb_cell = [c for c in cells if c.board == BoardType.HALF_BOARD][0]

    assert ai_cell.country == "GR"
    assert ai_cell.month == "2026-07"
    assert hb_cell.country == "GR"
    assert hb_cell.month == "2026-07"


@pytest.mark.asyncio
async def test_update_cell_activations():
    cells_repo = MagicMock()
    cells_repo.activate_cells = AsyncMock(return_value={})
    cells_repo.decrement_activations = AsyncMock()

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
    call_order = []

    async def record_activate(cells):
        call_order.append("activate")
        return {}

    async def record_decrement(cell_ids):
        call_order.append("decrement")

    cells_repo.activate_cells = AsyncMock(side_effect=record_activate)
    cells_repo.decrement_activations = AsyncMock(side_effect=record_decrement)

    await service.update_cell_activations(new_prefs, old_prefs, ref)

    assert call_order == ["activate", "decrement"]
    cells_repo.decrement_activations.assert_called_once()
    dec_args = cells_repo.decrement_activations.call_args[0][0]
    assert len(dec_args) == 1

    cells_repo.activate_cells.assert_called_once()
    activated_cells = cells_repo.activate_cells.call_args[0][0]
    assert len(activated_cells) == 1
    assert activated_cells[0].country == "IT"


@pytest.mark.asyncio
async def test_update_cell_activations_creates_missing_cell():
    cells_repo = MagicMock()
    cells_repo.activate_cells = AsyncMock(return_value={})

    service = ActivationService(cells_repo)

    new_prefs = UserPreferences(
        countries=["GR"],
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    ref = date(2026, 6, 15)
    await service.update_cell_activations(new_prefs, None, ref)

    cells_repo.activate_cells.assert_called_once()
    created_cell = cells_repo.activate_cells.call_args[0][0][0]
    assert isinstance(created_cell, MarketCell)
    assert created_cell.country == "GR"
    assert created_cell.month == "2026-07"
    assert created_cell.activation_count == 1
