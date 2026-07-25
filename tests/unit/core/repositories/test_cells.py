import pytest
from datetime import datetime

from core.exceptions.repository import ItemNotFoundException
from core.models.cell import MarketCell
from core.models.common import BoardType
from core.repositories.cells import DynamoCellsRepository

pytestmark = pytest.mark.asyncio


async def test_cells_repo_lifecycle(cells_table):
    repo = DynamoCellsRepository(cells_table)

    cell = MarketCell(
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    await repo.put(cell)
    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.cell_id == cell.cell_id
    assert fetched.country == "MX"
    assert fetched.activation_count == 1

    all_cells: list[MarketCell] = await repo.scan()
    assert len(all_cells) == 1
    assert all_cells[0].cell_id == cell.cell_id

    res = await repo.increment_activations([cell.cell_id])
    assert res == {cell.cell_id: 2}

    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.activation_count == 2

    now = datetime(2026, 6, 17, 12, 0, 0)
    await repo.update_last_scraped([cell.cell_id], now)
    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.last_scraped_at == now

    res = await repo.decrement_activations([cell.cell_id])
    assert res == {cell.cell_id: 1}

    res = await repo.decrement_activations([cell.cell_id])
    assert res == {cell.cell_id: 0}

    fetched = await repo.get(cell.cell_id)
    assert fetched is None

    all_cells: list[MarketCell] = await repo.scan()
    assert len(all_cells) == 0


async def test_cells_repo_delete(cells_table):
    repo = DynamoCellsRepository(cells_table)

    cell = MarketCell(
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    await repo.put(cell)
    assert await repo.get(cell.cell_id) is not None

    await repo.delete(cell.cell_id)
    assert await repo.get(cell.cell_id) is None


async def test_cells_repo_increment_raises_when_cell_missing(cells_table):
    repo = DynamoCellsRepository(cells_table)

    with pytest.raises(ItemNotFoundException, match="Cell not found: missing-cell"):
        await repo.increment_activations(["missing-cell"])


async def test_cells_repo_activate_cells_creates_and_increments(cells_table):
    repo = DynamoCellsRepository(cells_table)

    cell = MarketCell(
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    first = await repo.activate_cells([cell])
    assert first == {cell.cell_id: 1}

    second = await repo.activate_cells([cell])
    assert second == {cell.cell_id: 2}

    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.activation_count == 2


async def test_cells_repo_activate_cells_concurrent_first_activation(cells_table):
    repo = DynamoCellsRepository(cells_table)

    cell = MarketCell(
        country="MX",
        month="2026-08",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    import asyncio

    results = await asyncio.gather(
        repo.activate_cells([cell]),
        repo.activate_cells([cell]),
    )
    assert sorted(result[cell.cell_id] for result in results) == [1, 2]

    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.activation_count == 2


async def test_cells_repo_decrement_raises_when_cell_missing(cells_table):
    repo = DynamoCellsRepository(cells_table)

    with pytest.raises(ItemNotFoundException, match="Cell not found: missing-cell"):
        await repo.decrement_activations(["missing-cell"])


async def test_cells_repo_update_last_scraped_does_not_create_missing_cell(cells_table):
    repo = DynamoCellsRepository(cells_table)

    now = datetime(2026, 6, 17, 12, 0, 0)
    await repo.update_last_scraped(["missing-cell-id"], now)

    assert await repo.get("missing-cell-id") is None
    assert await repo.scan() == []
