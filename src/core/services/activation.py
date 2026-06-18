from datetime import date

from core.models.cell import MarketCell
from core.models.user import UserPreferences
from core.repositories.base import CellsRepository


def resolve_months_for_range(
    date_from: date | None,
    date_to: date | None,
    reference_date: date | None = None,
) -> list[str]:
    """Resolve YYYY-MM month strings based on the user's travel date range.
    If dates are not configured, return the current month and the next 8 months (9 months total).
    """
    ref = reference_date or date.today()

    if date_from is None and date_to is None:
        start_year = ref.year
        start_month = ref.month
        months = []
        for _ in range(9):
            months.append(f"{start_year:04d}-{start_month:02d}")
            start_month += 1
            if start_month > 12:
                start_month = 1
                start_year += 1
        return months

    start_date = date_from if date_from is not None else ref
    # Clip start_date to reference date if it's in the past
    start_date = max(start_date, ref)

    if date_to is not None:
        end_date = max(date_to, start_date)
    else:
        end_year = start_date.year
        end_month = start_date.month + 8
        while end_month > 12:
            end_month -= 12
            end_year += 1
        end_date = date(end_year, end_month, 1)

    months = []
    curr_year = start_date.year
    curr_month = start_date.month
    end_year = end_date.year
    end_month = end_date.month

    while (curr_year, curr_month) <= (end_year, end_month):
        months.append(f"{curr_year:04d}-{curr_month:02d}")
        curr_month += 1
        if curr_month > 12:
            curr_month = 1
            curr_year += 1

    return months


def generate_required_cells(
    preferences: UserPreferences,
    reference_date: date | None = None,
) -> list[MarketCell]:
    """Generate the set of candidate MarketCell instances required by the UserPreferences."""
    ref = reference_date or date.today()
    months = resolve_months_for_range(preferences.date_from, preferences.date_to, ref)

    cells = []
    for country in preferences.countries:
        for month in months:
            cells.append(
                MarketCell(
                    country=country,
                    month=month,
                    min_stars=preferences.min_stars,
                    board=preferences.board,
                    adults=preferences.adults,
                    children=len(preferences.children),
                    activation_count=1,
                )
            )
    return cells


class ActivationService:
    """Handles incrementing and decrementing activation references for MarketCells in the system."""

    def __init__(self, cells_repo: CellsRepository) -> None:
        self.cells_repo = cells_repo

    async def update_cell_activations(
        self,
        new_prefs: UserPreferences,
        old_prefs: UserPreferences | None,
        new_reference_date: date | None = None,
        old_reference_date: date | None = None,
    ) -> None:
        """Increment activation counts for new cells and decrement for obsolete ones."""
        new_ref = new_reference_date or date.today()
        old_ref = old_reference_date or new_ref

        new_cells = {
            cell.cell_id: cell for cell in generate_required_cells(new_prefs, new_ref)
        }

        if old_prefs is None:
            old_cell_ids = set()
        else:
            old_cell_ids = {
                cell.cell_id for cell in generate_required_cells(old_prefs, old_ref)
            }

        new_cell_ids = set(new_cells.keys())
        to_activate_ids = new_cell_ids - old_cell_ids
        to_deactivate_ids = old_cell_ids - new_cell_ids

        # 1. Decrement obsolete cells
        if to_deactivate_ids:
            await self.cells_repo.decrement_activations(list(to_deactivate_ids))

        # 2. Atomically create or increment new cells
        if to_activate_ids:
            cells_to_activate = [new_cells[cell_id] for cell_id in to_activate_ids]
            await self.cells_repo.activate_cells(cells_to_activate)
