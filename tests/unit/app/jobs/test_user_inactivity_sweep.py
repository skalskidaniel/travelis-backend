from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.user_inactivity_sweep import run_user_inactivity_sweep


@pytest.fixture
def mock_container():
    c = MagicMock()
    c.user_activity_service.sweep = AsyncMock(return_value={"users": 3, "cells": 12})
    return c


@pytest.mark.asyncio
async def test_run_user_inactivity_sweep_returns_stats(mock_container):
    result = await run_user_inactivity_sweep(mock_container)

    assert result == {"users": 3, "cells": 12}
    mock_container.user_activity_service.sweep.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_user_inactivity_sweep_handles_empty(mock_container):
    mock_container.user_activity_service.sweep = AsyncMock(
        return_value={"users": 0, "cells": 0}
    )

    result = await run_user_inactivity_sweep(mock_container)

    assert result == {"users": 0, "cells": 0}


@pytest.mark.asyncio
async def test_run_user_inactivity_sweep_propagates_errors(mock_container):
    mock_container.user_activity_service.sweep = AsyncMock(
        side_effect=RuntimeError("dynamo unavailable")
    )

    with pytest.raises(RuntimeError, match="dynamo unavailable"):
        await run_user_inactivity_sweep(mock_container)
