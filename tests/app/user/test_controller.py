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
    c.activation_service = AsyncMock()
    c.scheduler_service = AsyncMock()
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


def test_get_preferences_new_user_lazy_creates(client, mock_container, auth_headers):
    # Mock user not found -> triggers get-or-create provisioning
    mock_container.users_repo.get.return_value = None

    response = client.get("/api/v2/user/preferences", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["min_stars"] == 2  # default value

    mock_container.users_repo.get.assert_called_once_with("user-123")
    mock_container.users_repo.put.assert_called_once()
    mock_container.activation_service.update_cell_activations.assert_called_once()
    mock_container.scheduler_service.schedule_match.assert_called_once_with("user-123")


def test_get_preferences_existing_user(client, mock_container, auth_headers):
    # Mock user exists
    existing_user = User(
        user_id="user-123", preferences=UserPreferences(min_stars=4, countries=["PL"])
    )
    mock_container.users_repo.get.return_value = existing_user

    response = client.get("/api/v2/user/preferences", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["min_stars"] == 4
    assert data["countries"] == ["PL"]

    mock_container.users_repo.get.assert_called_once_with("user-123")
    mock_container.users_repo.put.assert_not_called()


def test_update_preferences(client, mock_container, auth_headers):
    existing_user = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user

    payload = {
        "min_stars": 5,
        "countries": ["IT", "ES"],
    }
    response = client.patch(
        "/api/v2/user/preferences", json=payload, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_stars"] == 5
    assert data["countries"] == ["IT", "ES"]

    mock_container.users_repo.put.assert_called_once()
    mock_container.activation_service.update_cell_activations.assert_called_once()
    mock_container.scheduler_service.schedule_match.assert_called_once_with("user-123")


def test_enable_push(client, mock_container, auth_headers):
    existing_user = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user

    payload = {
        "subscription": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/token123",
            "keys": {"p256dh": "key_p256dh", "auth": "key_auth"},
        }
    }
    response = client.post(
        "/api/v2/user/push/enable", json=payload, headers=auth_headers
    )

    assert response.status_code == 204
    mock_container.users_repo.update_push.assert_called_once()
    args, kwargs = mock_container.users_repo.update_push.call_args
    assert args[0] == "user-123"
    assert kwargs["enabled"] is True
    assert (
        kwargs["subscription"].endpoint
        == "https://fcm.googleapis.com/fcm/send/token123"
    )
    assert kwargs["subscription"].keys.p256dh == "key_p256dh"
    assert kwargs["subscription"].keys.auth == "key_auth"


def test_disable_push(client, mock_container, auth_headers):
    existing_user = User(user_id="user-123")
    mock_container.users_repo.get.return_value = existing_user

    response = client.post("/api/v2/user/push/disable", headers=auth_headers)

    assert response.status_code == 204
    mock_container.users_repo.update_push.assert_called_once_with(
        "user-123", enabled=False, subscription=None
    )
