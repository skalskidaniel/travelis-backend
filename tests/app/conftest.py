import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_headers(client):
    response = client.get(
        "/api/v2/health",
        headers={
            "Origin": "https://wakacje-travelis.pl",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] in [
        "*",
        "https://wakacje-travelis.pl",
    ]
