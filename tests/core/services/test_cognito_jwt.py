import time

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from core.config import Settings
from core.exceptions.cognito import (
    CognitoJwtConfigurationException,
    CognitoJwtValidationException,
)
from core.services.cognito_jwt import CognitoJwtVerifier


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


def _encode_token(
    private_pem: bytes,
    *,
    kid: str | None = "test-key-id",
    drop_claims: tuple[str, ...] = (),
    **claims,
) -> str:
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
    for claim in drop_claims:
        payload.pop(claim, None)
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers=headers,
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


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_expired_token(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], exp=int(time.time()) - 1)

        with pytest.raises(CognitoJwtValidationException, match="Invalid token"):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_wrong_issuer(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], iss="https://example.com/wrong")

        with pytest.raises(CognitoJwtValidationException, match="Invalid token"):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_missing_issuer(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], drop_claims=("iss",))

        with pytest.raises(CognitoJwtValidationException, match="Invalid token"):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_missing_kid_header(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], kid=None)

        with pytest.raises(CognitoJwtValidationException, match="missing kid header"):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_missing_token_use(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], drop_claims=("token_use",))

        with pytest.raises(
            CognitoJwtValidationException, match='missing the "token_use" claim'
        ):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_invalid_token_use(
    cognito_settings, rsa_keys, jwks_payload
):
    respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).respond(json=jwks_payload)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], token_use="refresh")

        with pytest.raises(
            CognitoJwtValidationException, match="Invalid token_use claim"
        ):
            await verifier.verify_token(token)


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_refreshes_jwks_on_unknown_kid(
    cognito_settings, rsa_keys, jwks_payload
):
    jwks_without_key = {"keys": []}
    jwks_route = respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).mock(
        side_effect=[
            httpx.Response(200, json=jwks_without_key),
            httpx.Response(200, json=jwks_payload),
        ]
    )

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], kid="test-key-id")
        user_id = await verifier.verify_token(token)

    assert user_id == "user-123"
    assert jwks_route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_verify_token_rejects_when_key_not_found_after_refresh(
    cognito_settings, rsa_keys
):
    jwks_route = respx.get(
        "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TestPool/.well-known/jwks.json"
    ).mock(
        side_effect=[
            httpx.Response(200, json={"keys": []}),
            httpx.Response(200, json={"keys": []}),
        ]
    )

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"], kid="missing-key")

        with pytest.raises(
            CognitoJwtValidationException, match="signing key not found"
        ):
            await verifier.verify_token(token)

    assert jwks_route.call_count == 2


@pytest.mark.asyncio
async def test_verify_token_raises_configuration_error_when_app_client_missing(
    cognito_settings, rsa_keys
):
    object.__setattr__(cognito_settings, "cognito_app_client_id", None)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"])

        with pytest.raises(
            CognitoJwtConfigurationException, match="COGNITO_APP_CLIENT_ID"
        ):
            await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_verify_token_raises_configuration_error_when_pool_id_missing(
    cognito_settings, rsa_keys
):
    object.__setattr__(cognito_settings, "cognito_user_pool_id", None)

    async with httpx.AsyncClient() as client:
        verifier = CognitoJwtVerifier(cognito_settings, client)
        token = _encode_token(rsa_keys["private_pem"])

        with pytest.raises(
            CognitoJwtConfigurationException, match="COGNITO_USER_POOL_ID"
        ):
            await verifier.verify_token(token)
