import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app.auth.dependencies import get_current_user

auth_test_app = FastAPI()


@auth_test_app.get("/test-auth")
def mock_auth_endpoint(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}


@pytest.fixture
def test_client():
    return TestClient(auth_test_app)


def test_get_current_user_valid_token(test_client):
    payload = {"sub": "user-123", "email": "test@example.com"}
    token = jwt.encode(payload, "a" * 32, algorithm="HS256")

    response = test_client.get(
        "/test-auth", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123"}


def test_get_current_user_missing_header(test_client):
    response = test_client.get("/test-auth")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_get_current_user_invalid_token(test_client):
    response = test_client.get(
        "/test-auth", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]
