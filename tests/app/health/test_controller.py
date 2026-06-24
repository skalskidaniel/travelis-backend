from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_container
from app.main import app
from core.container import Container


@pytest.fixture
def mock_container():
    c = MagicMock(spec=Container)
    c.settings = MagicMock()
    c.settings.users_table = "test-users"
    c.redis_client = AsyncMock()
    c.redis_client.ping = AsyncMock(return_value=True)
    c.users_repo = MagicMock()
    c.users_repo.table = MagicMock()
    c.users_repo.table.meta = MagicMock()
    c.users_repo.table.meta.client = MagicMock()
    c.users_repo.table.meta.client.describe_table = AsyncMock(return_value={})
    return c


@pytest.fixture
def client(mock_container):
    app.dependency_overrides[get_container] = lambda: mock_container
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_check_returns_ok(client):
    response = client.get("/api/v2/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"redis": "ok", "dynamodb": "ok"},
    }


def test_health_check_redis_error(client, mock_container):
    mock_container.redis_client.ping = AsyncMock(side_effect=ConnectionError("down"))

    response = client.get("/api/v2/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["redis"] == "error"
    assert body["checks"]["dynamodb"] == "ok"


def test_health_check_dynamodb_unavailable(client, mock_container):
    mock_container.users_repo = None

    response = client.get("/api/v2/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["dynamodb"] == "unavailable"
