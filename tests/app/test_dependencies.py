import pytest
from unittest.mock import AsyncMock

from app.dependencies import (
    get_container,
    get_users_repo,
    get_cells_repo,
    get_offers_repo,
    get_user_offers_repo,
    get_feed_repo,
    get_activation_service,
    get_matching_service,
    get_scheduler_service,
)
from core.container import container, Container


@pytest.mark.asyncio
async def test_get_container_initializes_lazily():
    # Setup
    container.exit_stack = None
    container.initialize = AsyncMock()

    # Execute
    c = await get_container()

    # Assert
    assert c is container
    container.initialize.assert_awaited_once()

    # Second call should not initialize again if exit_stack is set
    container.exit_stack = AsyncMock()
    container.initialize.reset_mock()
    c = await get_container()
    assert c is container
    container.initialize.assert_not_awaited()

    # Cleanup
    container.exit_stack = None


@pytest.mark.asyncio
async def test_getters_return_correct_attributes():
    mock_container = AsyncMock(spec=Container)
    
    # We assign mock attributes matching what the getters expect
    mock_container.users_repo = "mock_users_repo"
    mock_container.cells_repo = "mock_cells_repo"
    mock_container.offers_repo = "mock_offers_repo"
    mock_container.user_offers_repo = "mock_user_offers_repo"
    mock_container.feed_repo = "mock_feed_repo"
    mock_container.activation_service = "mock_activation_service"
    mock_container.matching_service = "mock_matching_service"
    mock_container.scheduler_service = "mock_scheduler_service"

    assert await get_users_repo(mock_container) == "mock_users_repo"
    assert await get_cells_repo(mock_container) == "mock_cells_repo"
    assert await get_offers_repo(mock_container) == "mock_offers_repo"
    assert await get_user_offers_repo(mock_container) == "mock_user_offers_repo"
    assert await get_feed_repo(mock_container) == "mock_feed_repo"
    assert await get_activation_service(mock_container) == "mock_activation_service"
    assert await get_matching_service(mock_container) == "mock_matching_service"
    assert await get_scheduler_service(mock_container) == "mock_scheduler_service"
