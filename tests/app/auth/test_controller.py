import jwt
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.dependencies import get_container
from core.models.user import User, UserPreferences


@pytest.fixture
def mock_container():
    c = MagicMock()
    c.users_repo = AsyncMock()
    c.cells_repo = AsyncMock()
    c.user_offers_repo = AsyncMock()
    c.feed_repo = AsyncMock()
    c.cognito_client = AsyncMock()
    c.settings = MagicMock()
    c.settings.cognito_user_pool_id = "test-pool-id"
    return c


@pytest.fixture
def client(mock_container):
    app.dependency_overrides[get_container] = lambda: mock_container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    payload = {"sub": "user-123"}
    token = jwt.encode(payload, "a" * 32, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_delete_account_cascade_success(client, mock_container, auth_headers):
    existing_user = User(
        user_id="user-123", preferences=UserPreferences(countries=["IT"])
    )
    mock_container.users_repo.get.return_value = existing_user

    mock_container.user_offers_repo.query_by_user.return_value = [
        {"user_id": "user-123", "offer_id": "offer-abc"}
    ]

    response = client.delete("/api/v2/auth/account", headers=auth_headers)

    assert response.status_code == 204

    mock_container.cells_repo.decrement_activations.assert_called_once()

    mock_container.user_offers_repo.delete_batch.assert_called_once_with(
        [("user-123", "offer-abc")]
    )

    mock_container.feed_repo.clear_user.assert_called_once_with("user-123")

    mock_container.users_repo.delete.assert_called_once_with("user-123")

    mock_container.cognito_client.admin_delete_user.assert_called_once_with(
        UserPoolId="test-pool-id", Username="user-123"
    )


def test_delete_account_user_not_found_cleans_cognito(
    client, mock_container, auth_headers
):
    mock_container.users_repo.get.return_value = None

    response = client.delete("/api/v2/auth/account", headers=auth_headers)

    assert response.status_code == 204

    mock_container.cells_repo.decrement_activations.assert_not_called()
    mock_container.user_offers_repo.delete_batch.assert_not_called()
    mock_container.feed_repo.clear_user.assert_not_called()
    mock_container.users_repo.delete.assert_not_called()

    mock_container.cognito_client.admin_delete_user.assert_called_once_with(
        UserPoolId="test-pool-id", Username="user-123"
    )


def test_delete_account_no_cognito_pool_skips_cognito(
    client, mock_container, auth_headers
):
    mock_container.settings.cognito_user_pool_id = None

    existing_user = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = []

    response = client.delete("/api/v2/auth/account", headers=auth_headers)

    assert response.status_code == 204

    mock_container.users_repo.delete.assert_called_once_with("user-123")

    mock_container.cognito_client.admin_delete_user.assert_not_called()
