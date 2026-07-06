from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.container import Container


@pytest.mark.asyncio
async def test_container_lifecycle():
    container = Container()

    mock_dynamo_resource = AsyncMock()
    mock_table = AsyncMock()
    mock_dynamo_resource.Table.return_value = mock_table

    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_session = MagicMock()
    mock_resource_cm = AsyncMock()
    mock_resource_cm.__aenter__.return_value = mock_dynamo_resource
    mock_session.resource.return_value = mock_resource_cm

    with (
        patch("core.container.aioboto3.Session", return_value=mock_session),
        patch("core.container.Redis.from_url", return_value=mock_redis),
    ):
        # Initial state
        assert container.exit_stack is None

        # Initialize
        await container.initialize()

        assert container.exit_stack is not None
        assert container.dynamodb_resource == mock_dynamo_resource
        assert container.redis_client == mock_redis
        assert container.users_repo is not None
        assert container.cells_repo is not None
        assert container.offers_repo is not None
        assert container.user_offers_repo is not None
        assert container.feed_repo is not None
        assert container.activation_service is not None
        assert container.notifications_service is not None
        assert container.matching_service is not None

        # Second initialize should be a no-op
        prev_stack = container.exit_stack
        await container.initialize()
        assert container.exit_stack is prev_stack

        # Cleanup
        await container.cleanup()

        assert container.exit_stack is None
        assert container.dynamodb_resource is None
        assert container.redis_client is None
        assert container.users_repo is None
        assert container.cells_repo is None
        assert container.offers_repo is None
        assert container.user_offers_repo is None
        assert container.feed_repo is None
        assert container.activation_service is None
        assert container.matching_service is None
        assert container.notifications_service is None
