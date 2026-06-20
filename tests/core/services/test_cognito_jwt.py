import time

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from core.config import Settings
from core.services.cognito_jwt import CognitoJwtValidationException, CognitoJwtVerifier


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = public_key.public_numbers()
    return {
        "private_pem": private_pem,
        "public_numbers": public_numbers,
    }


@pytest.fixture
def jwks_payload(rsa_keys):
    public_numbers = rsa_keys["public_numbers"]
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-id",
                "use": "sig",
                "alg": "RS256",
                "n": jwt.utils.base64url_encode(
                    public_numbers.n.to_bytes(
                        (public_numbers.n.bit_length() + 7) // 8, "big"
                    )
                ).decode(),
                "e": jwt.utils.base64url_encode(
                    public_numbers.e.to_bytes(
                        (public_numbers.e.bit_length() + 7) // 8, "big"
                    )
                ).decode(),
            }
        ]
    }


@pytest.fixture
def cognito_settings(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-central-1_TestPool")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "test-app-client-id")
    return Settings()


def _encode_token(private_pem: bytes, **claims) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-123",
        "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool",
        "token_use": "access",
        "client_id": "test-app-client-id",
        "exp": now + 3600,
        "iat": now,
        **claims,
    }
    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-id"},
    )


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_accepts_valid_access_token(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"])
        user_id = await verifier.verify_token(token)

    assert user_id == "user-123"


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_forged_token(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(other_pem)

        with pytest.raises(CognitoJwtValidationException, match="Invalid token"):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_wrong_client_id(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], client_id="wrong-client")

        with pytest.raises(CognitoJwtValidationException, match="client_id"):
            await verifier.verify_token(token)
