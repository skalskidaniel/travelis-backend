import jwt
import pytest
import fakeredis
from unittest.mock import MagicMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.dependencies import get_container
from app.rate_limiter import RateLimiter
from core.container import Container

# Create a test FastAPI application
limiter_test_app = FastAPI()


@limiter_test_app.get(
    "/limit-ip", dependencies=[Depends(RateLimiter(times=2, seconds=10))]
)
async def limit_ip_endpoint():
    return {"status": "ok"}


@limiter_test_app.get(
    "/limit-user", dependencies=[Depends(RateLimiter(times=2, seconds=10))]
)
async def limit_user_endpoint():
    return {"status": "ok"}


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def mock_container(fake_redis):
    # Create a mock Container that returns the fake_redis client
    container_mock = MagicMock(spec=Container)
    container_mock.redis_client = fake_redis
    container_mock.settings = MagicMock()
    container_mock.settings.rate_limiting_enabled = True
    return container_mock


@pytest.fixture
def client(mock_container):
    limiter_test_app.dependency_overrides[get_container] = lambda: mock_container
    with TestClient(limiter_test_app) as c:
        yield c
    limiter_test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rate_limiter_passes_under_limit(client):
    # Perform first two requests (limit is 2)
    response1 = client.get("/limit-ip")
    assert response1.status_code == 200
    assert response1.json() == {"status": "ok"}

    response2 = client.get("/limit-ip")
    assert response2.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_exceeds_limit(client):
    # First request
    client.get("/limit-ip")
    # Second request
    client.get("/limit-ip")
    # Third request (should exceed)
    response = client.get("/limit-ip")
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_rate_limiter_by_user_id(client):
    # We will forge JWT tokens with different subs
    token1 = jwt.encode({"sub": "user_a"}, "secret", algorithm="HS256")
    token2 = jwt.encode({"sub": "user_b"}, "secret", algorithm="HS256")

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User A consumes their limit (2 requests)
    assert client.get("/limit-user", headers=headers1).status_code == 200
    assert client.get("/limit-user", headers=headers1).status_code == 200
    assert client.get("/limit-user", headers=headers1).status_code == 429

    # User B is still under their limit and should be allowed
    assert client.get("/limit-user", headers=headers2).status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_disabled_globally(client, mock_container):
    mock_container.settings.rate_limiting_enabled = False

    # Perform 5 requests (exceeding limit of 2)
    for _ in range(5):
        response = client.get("/limit-ip")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_redis_error(
    client, mock_container, fake_redis
):
    # Force fake_redis to raise an error when incrementing or processing commands
    # We do this by mocking redis_client.pipeline to raise a connection/runtime error
    mock_pipeline = MagicMock()
    mock_pipeline.incr.side_effect = Exception("Redis connection failed")
    mock_container.redis_client.pipeline = MagicMock(return_value=mock_pipeline)

    # Rate limiter should fail open gracefully
    response1 = client.get("/limit-ip")
    assert response1.status_code == 200
    assert response1.json() == {"status": "ok"}
