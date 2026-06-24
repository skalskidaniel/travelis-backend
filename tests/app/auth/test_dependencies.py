import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.exceptions import AuthenticationException, ServiceConfigurationException
from core.config import Settings
from core.exceptions.cognito import (
    CognitoJwtConfigurationException,
    CognitoJwtValidationException,
)
from core.services.cognito_jwt import CognitoJwtVerifier

auth_test_app = FastAPI()


@auth_test_app.exception_handler(AuthenticationException)
async def authentication_exception_handler(request, exc: AuthenticationException):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=401, content={"detail": str(exc)})


@auth_test_app.exception_handler(ServiceConfigurationException)
async def service_configuration_exception_handler(
    request, exc: ServiceConfigurationException
):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=500, content={"detail": str(exc)})


@auth_test_app.get("/test-auth")
async def mock_auth_endpoint(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = public_key.public_numbers()
    n = public_numbers.n
    e = public_numbers.e

    def int_to_base64url(value: int) -> str:
        byte_length = (value.bit_length() + 7) // 8
        import base64

        return (
            base64.urlsafe_b64encode(value.to_bytes(byte_length, "big"))
            .rstrip(b"=")
            .decode("ascii")
        )

    jwk = {
        "kty": "RSA",
        "kid": "test-key-id",
        "use": "sig",
        "alg": "RS256",
        "n": int_to_base64url(n),
        "e": int_to_base64url(e),
    }
    return private_pem, jwk


@pytest.fixture
def cognito_settings(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-central-1_TestPool")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "test-client-id")
    return Settings()


def _make_token(private_pem: bytes, **claims) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-123",
        "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool",
        "token_use": "id",
        "aud": "test-client-id",
        "exp": now + 3600,
        "iat": now,
        **claims,
    }
    headers = {"kid": "test-key-id"}
    return jwt.encode(payload, private_pem, algorithm="RS256", headers=headers)


@pytest.fixture
def verifier(cognito_settings, rsa_keypair):
    private_pem, jwk = rsa_keypair
    http_client = AsyncMock()
    response = MagicMock()
    response.json.return_value = {"keys": [jwk]}
    response.raise_for_status = MagicMock()
    http_client.get = AsyncMock(return_value=response)
    return CognitoJwtVerifier(
        settings=cognito_settings, http_client=http_client
    ), private_pem


@pytest.fixture
def test_client(verifier):
    verifier_instance, _ = verifier

    container = MagicMock()
    container.cognito_jwt_verifier = verifier_instance

    auth_test_app.dependency_overrides[get_container] = lambda: container
    with TestClient(auth_test_app) as client:
        yield client
    auth_test_app.dependency_overrides.clear()


def test_get_current_user_valid_token(test_client, verifier):
    _, private_pem = verifier
    token = _make_token(private_pem)

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


def test_get_current_user_configuration_error_returns_500():
    verifier = AsyncMock()
    verifier.verify_token = AsyncMock(
        side_effect=CognitoJwtConfigurationException(
            "COGNITO_APP_CLIENT_ID is not configured"
        )
    )
    container = MagicMock()
    container.cognito_jwt_verifier = verifier

    auth_test_app.dependency_overrides[get_container] = lambda: container
    with TestClient(auth_test_app) as client:
        response = client.get(
            "/test-auth", headers={"Authorization": "Bearer test-token"}
        )
    auth_test_app.dependency_overrides.clear()

    assert response.status_code == 500
    assert "COGNITO_APP_CLIENT_ID is not configured" in response.json()["detail"]


def test_get_current_user_rejects_forged_signature(verifier):
    verifier_instance, private_pem = verifier
    token = _make_token(private_pem)

    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_pem = attacker_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    forged_token = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        attacker_pem,
        algorithm="RS256",
        headers={"kid": "test-key-id"},
    )

    with pytest.raises(CognitoJwtValidationException, match="Invalid token"):
        import asyncio

        asyncio.run(verifier_instance.verify_token(forged_token))


def test_get_current_user_rejects_wrong_audience(verifier):
    verifier_instance, private_pem = verifier
    token = _make_token(private_pem, aud="wrong-client-id")

    with pytest.raises(CognitoJwtValidationException, match="audience"):
        import asyncio

        asyncio.run(verifier_instance.verify_token(token))


@pytest.mark.asyncio
async def test_verify_access_token_with_client_id(verifier):
    verifier_instance, private_pem = verifier
    token = _make_token(
        private_pem,
        token_use="access",
        client_id="test-client-id",
    )
    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool",
            "token_use": "access",
            "client_id": "test-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        },
        private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-id"},
    )

    user_id = await verifier_instance.verify_token(token)
    assert user_id == "user-123"
