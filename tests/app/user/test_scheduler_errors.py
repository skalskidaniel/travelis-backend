import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.main import app
from core.exceptions.scheduler import ScheduleCreateException

from core.models.user import User


@pytest.fixture
def mock_container():
    c = MagicMock()
    c.users_repo = AsyncMock()
    c.activation_service = AsyncMock()
    c.scheduler_service = AsyncMock()
    return c


@pytest.fixture
def client(mock_container):
    app.dependency_overrides[get_container] = lambda: mock_container
    app.dependency_overrides[get_current_user] = lambda: "user-123"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_update_preferences_returns_503_when_scheduler_fails(client, mock_container):
    existing_user = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.scheduler_service.schedule_match.side_effect = (
        ScheduleCreateException("Failed to create match schedule")
    )

    response = client.patch(
        "/api/v2/user/preferences",
        json={"min_stars": 5},
    )

    assert response.status_code == 503
    assert response.json()["retryable"] is True
