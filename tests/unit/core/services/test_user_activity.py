from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models.user import User, UserPreferences
from core.services.activation import generate_required_cells
from core.services.user_activity import UserActivityService


def _make_service(session_gap_minutes: int = 30):
    return UserActivityService(
        users_repo=MagicMock(),
        cells_repo=MagicMock(),
        redis_client=MagicMock(),
        inactivity_threshold_days=7,
        session_gap_minutes=session_gap_minutes,
    )


@pytest.mark.asyncio
async def test_touch_continuing_session_is_noop():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=datetime.now(timezone.utc).isoformat())
    service.users_repo.get = AsyncMock()
    service.users_repo.record_session_start = AsyncMock()

    await service.touch("user-1")

    service.redis.set.assert_awaited_once()
    _, kwargs = service.redis.set.await_args
    assert kwargs["ex"] == 30 * 60
    assert kwargs["get"] is True
    service.users_repo.get.assert_not_called()
    service.users_repo.record_session_start.assert_not_called()


@pytest.mark.asyncio
async def test_touch_session_boundary_records_session_start():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=None)
    prior_last_active = datetime(2026, 6, 1, tzinfo=timezone.utc)
    service.users_repo.get = AsyncMock(
        return_value=User(user_id="user-1", last_active_at=prior_last_active)
    )
    service.users_repo.record_session_start = AsyncMock()

    await service.touch("user-1")

    service.users_repo.get.assert_awaited_once_with("user-1")
    service.users_repo.record_session_start.assert_awaited_once()
    _, kwargs = service.users_repo.record_session_start.await_args
    assert kwargs["new_since"] == prior_last_active
    assert isinstance(kwargs["last_active_at"], datetime)


@pytest.mark.asyncio
async def test_touch_session_boundary_skips_missing_user():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=None)
    service.users_repo.get = AsyncMock(return_value=None)
    service.users_repo.record_session_start = AsyncMock()

    await service.touch("user-1")

    service.users_repo.record_session_start.assert_not_called()


@pytest.mark.asyncio
async def test_touch_swallows_repo_error():
    service = _make_service()
    service.redis.set = AsyncMock(return_value=None)
    service.users_repo.get = AsyncMock(side_effect=RuntimeError("dynamo unavailable"))
    service.users_repo.record_session_start = AsyncMock()

    await service.touch("user-1")


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

    before = datetime.now(timezone.utc)
    await service.sweep()
    after = datetime.now(timezone.utc)

    call_args = service.users_repo.list_users_inactive_since.await_args.args[0]
    assert isinstance(call_args, datetime)
    assert before - timedelta(days=14) <= call_args <= after - timedelta(days=14)
