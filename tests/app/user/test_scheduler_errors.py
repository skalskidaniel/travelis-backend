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


def test_update_preferences_succeeds_when_scheduler_fails(client, mock_container):
    existing_user: User = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.scheduler_service.schedule_match.side_effect = (
        ScheduleCreateException("Failed to create match schedule")
    )

    response = client.patch(
        "/v2/user/preferences",
        json={"min_stars": 5},
    )

    # The request should succeed with 200 because database changes were applied
    assert response.status_code == 200
    data = response.json()
    assert data["min_stars"] == 5
    mock_container.users_repo.put.assert_called_once()
    mock_container.scheduler_service.schedule_match.assert_called_once_with("user-123")


def test_get_preferences_succeeds_when_scheduler_fails(client, mock_container):
    # Mock lazy provisioning of new user
    mock_container.users_repo.get.return_value = None
    mock_container.scheduler_service.schedule_match.side_effect = (
        ScheduleCreateException("Failed to create match schedule")
    )

    response = client.get("/v2/user/preferences")

    # The request should succeed with 200 because user is successfully created in DynamoDB
    assert response.status_code == 200
    data = response.json()
    assert data["min_stars"] == 2  # Default preference value
    mock_container.users_repo.put.assert_called_once()
    mock_container.scheduler_service.schedule_match.assert_called_once_with("user-123")


def test_global_scheduler_exception_handler_sanitizes_errors(client, mock_container):
    # Mock users_repo.get to raise SchedulerException so that it propagates to the global exception handler
    mock_container.users_repo.get.side_effect = ScheduleCreateException(
        "Failed to create match schedule: LAMBDA_FUNCTION_ARN is missing"
    )

    response = client.get("/v2/user/preferences")

    # Should raise 503 and sanitize the message
    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Service temporarily unavailable"
    assert data["retryable"] is True
