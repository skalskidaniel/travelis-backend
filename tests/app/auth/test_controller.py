from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.main import app
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
    app.dependency_overrides[get_current_user] = lambda: "user-123"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_delete_account_cascade_success(client, mock_container):
    existing_user: User = User(
        user_id="user-123", preferences=UserPreferences(countries=["IT"])
    )
    mock_container.users_repo.get.return_value = existing_user

    mock_container.user_offers_repo.query_by_user.return_value = [
        {"user_id": "user-123", "offer_id": "offer-abc"}
    ]

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 204

    mock_container.user_offers_repo.delete_batch.assert_called_once_with(
        [("user-123", "offer-abc")]
    )

    mock_container.feed_repo.clear_user.assert_called_once_with("user-123")

    mock_container.users_repo.delete.assert_called_once_with("user-123")

    mock_container.cells_repo.decrement_activations.assert_called_once()

    mock_container.cognito_client.admin_delete_user.assert_called_once_with(
        UserPoolId="test-pool-id", Username="user-123"
    )


def test_delete_account_user_not_found_cleans_cognito(client, mock_container):
    mock_container.users_repo.get.return_value = None

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 204

    mock_container.cells_repo.decrement_activations.assert_not_called()
    mock_container.user_offers_repo.delete_batch.assert_not_called()
    mock_container.feed_repo.clear_user.assert_not_called()
    mock_container.users_repo.delete.assert_not_called()

    mock_container.cognito_client.admin_delete_user.assert_called_once_with(
        UserPoolId="test-pool-id", Username="user-123"
    )


def test_delete_account_no_cognito_pool_skips_cognito(client, mock_container):
    mock_container.settings.cognito_user_pool_id = None

    existing_user: User = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = []

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 204

    mock_container.users_repo.delete.assert_called_once_with("user-123")

    mock_container.cognito_client.admin_delete_user.assert_not_called()


def test_delete_account_fails_when_user_delete_fails(client, mock_container):
    existing_user: User = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = []
    mock_container.users_repo.delete.side_effect = RuntimeError("dynamodb error")

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 500
    assert "retryable" not in response.json()
    mock_container.cells_repo.decrement_activations.assert_not_called()
    mock_container.cognito_client.admin_delete_user.assert_not_called()


def test_delete_account_fails_when_cognito_delete_fails(client, mock_container):
    existing_user: User = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = []
    mock_container.cognito_client.admin_delete_user.side_effect = RuntimeError(
        "cognito error"
    )

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 500
    assert "retryable" not in response.json()
    mock_container.users_repo.delete.assert_called_once_with("user-123")
    mock_container.cells_repo.decrement_activations.assert_called_once()


def test_delete_account_fails_when_user_offers_delete_fails_no_cell_decrement(
    client, mock_container
):
    existing_user: User = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = [
        {"user_id": "user-123", "offer_id": "offer-abc"}
    ]
    mock_container.user_offers_repo.delete_batch.side_effect = RuntimeError(
        "dynamodb error"
    )

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 500
    mock_container.feed_repo.clear_user.assert_not_called()
    mock_container.users_repo.delete.assert_not_called()
    mock_container.cells_repo.decrement_activations.assert_not_called()


def test_delete_account_uses_updated_at_reference_date(client, mock_container):
    updated_at = datetime(2025, 3, 15, 12, 0, tzinfo=timezone.utc)
    existing_user: User = User(
        user_id="user-123",
        preferences=UserPreferences(countries=["IT"]),
        updated_at=updated_at,
    )
    mock_container.users_repo.get.return_value = existing_user
    mock_container.user_offers_repo.query_by_user.return_value = []

    response = client.delete("/api/v2/auth/account")

    assert response.status_code == 204
    mock_container.cells_repo.decrement_activations.assert_called_once()
