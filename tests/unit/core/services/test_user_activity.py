from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models.user import User, UserPreferences
from core.services.activation import generate_required_cells
from core.services.user_activity import (
    UserActivityService,
    seconds_until_next_utc_midnight,
)


def test_seconds_until_next_utc_midnight_is_positive():
    secs = seconds_until_next_utc_midnight()
    assert 1 <= secs <= 86400


def test_seconds_until_next_utc_midnight_at_midnight_is_full_day():
    midnight = datetime(2026, 6, 25, 0, 0, 0, tzinfo=timezone.utc)
    secs = seconds_until_next_utc_midnight(midnight)
    assert secs == 86400


def test_seconds_until_next_utc_midnight_just_before_midnight_is_small():
    almost = datetime(2026, 6, 25, 23, 59, 59, tzinfo=timezone.utc)
    secs = seconds_until_next_utc_midnight(almost)
    assert secs == 1


def _make_service():
    return UserActivityService(
        users_repo=MagicMock(),
        cells_repo=MagicMock(),
        redis_client=MagicMock(),
        inactivity_threshold_days=7,
    )


@pytest.mark.asyncio
async def test_touch_daily_first_call_writes_to_repo():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=True)
    service.users_repo.touch_last_seen = AsyncMock()

    await service.touch_daily("user-1")

    service.redis.set.assert_awaited_once()
    service.users_repo.touch_last_seen.assert_awaited_once_with("user-1", date.today())


@pytest.mark.asyncio
async def test_touch_daily_second_call_is_noop():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=None)
    service.users_repo.touch_last_seen = AsyncMock()

    await service.touch_daily("user-1")

    service.redis.set.assert_awaited_once()
    service.users_repo.touch_last_seen.assert_not_called()


@pytest.mark.asyncio
async def test_touch_daily_swallows_repo_error():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=True)
    service.users_repo.touch_last_seen = AsyncMock(
        side_effect=RuntimeError("dynamo unavailable")
    )

    await service.touch_daily("user-1")


@pytest.mark.asyncio
async def test_ensure_active_returns_false_for_active_user():
    service = _make_service()
    service.users_repo.clear_inactive = AsyncMock()
    service.cells_repo.activate_cells = AsyncMock()

    user = User(user_id="user-1", is_active=True)
    result = await service.ensure_active(user)

    assert result is False
    service.users_repo.clear_inactive.assert_not_called()
    service.cells_repo.activate_cells.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_active_reactivates_inactive_user():
    service = _make_service()
    service.users_repo.clear_inactive = AsyncMock(return_value=1)
    service.cells_repo.activate_cells = AsyncMock(return_value={})

    prefs = UserPreferences(countries=["GR"])
    user = User(user_id="user-1", preferences=prefs, is_active=False)
    result = await service.ensure_active(user)

    assert result is True
    service.users_repo.clear_inactive.assert_awaited_once_with(["user-1"])
    expected_cells = generate_required_cells(prefs)
    expected_cell_ids = [c.cell_id for c in expected_cells]
    service.cells_repo.activate_cells.assert_awaited_once()
    activated_cells_arg = service.cells_repo.activate_cells.await_args.args[0]
    assert [c.cell_id for c in activated_cells_arg] == expected_cell_ids


@pytest.mark.asyncio
async def test_sweep_no_inactive_users():
    service = _make_service()
    service.users_repo.list_users_inactive_since = AsyncMock(return_value=[])

    stats = await service.sweep()

    assert stats == {"users": 0, "cells": 0}
    service.cells_repo.decrement_activations.assert_not_called()
    service.users_repo.mark_inactive.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_decrements_cells_and_marks_inactive():
    service = _make_service()
    inactive_users = [
        User(user_id=f"user-{i}", preferences=UserPreferences(countries=["GR"]))
        for i in range(2)
    ]
    service.users_repo.list_users_inactive_since = AsyncMock(
        return_value=inactive_users
    )
    service.users_repo.mark_inactive = AsyncMock(return_value=2)
    service.cells_repo.decrement_activations = AsyncMock(return_value={})

    stats = await service.sweep()

    assert stats["users"] == 2
    expected_cells = sum(
        len(generate_required_cells(u.preferences)) for u in inactive_users
    )
    assert stats["cells"] == expected_cells
    service.cells_repo.decrement_activations.assert_awaited_once()
    service.users_repo.mark_inactive.assert_awaited_once_with(["user-0", "user-1"])


@pytest.mark.asyncio
async def test_sweep_uses_threshold_for_cutoff():
    service = UserActivityService(
        users_repo=MagicMock(),
        cells_repo=MagicMock(),
        redis_client=MagicMock(),
        inactivity_threshold_days=14,
    )
    service.users_repo.list_users_inactive_since = AsyncMock(return_value=[])
    service.cells_repo.decrement_activations = AsyncMock(return_value={})
    service.users_repo.mark_inactive = AsyncMock(return_value=0)

    await service.sweep()

    call_args = service.users_repo.list_users_inactive_since.await_args.args[0]
    expected_cutoff = date.today().toordinal() - 14
    assert call_args.toordinal() == expected_cutoff
