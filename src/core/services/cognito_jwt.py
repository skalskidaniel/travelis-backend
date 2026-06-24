from aws_lambda_powertools import Logger
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from core.config import Settings
from core.exceptions.cognito import (
    CognitoJwtConfigurationException,
    CognitoJwtValidationException,
)

logger = Logger(child=True)


class CognitoJwtVerifier:
    """Validates Cognito-issued JWTs using JWKS from the user pool."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client
        self._jwks_keys: dict[str, dict[str, Any]] | None = None

    @property
    def issuer(self) -> str:
        pool_id = self.settings.cognito_user_pool_id
        if not pool_id:
            raise CognitoJwtConfigurationException(
                "COGNITO_USER_POOL_ID is not configured"
            )
        return f"https://cognito-idp.{self.settings.aws_region}.amazonaws.com/{pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

    async def _fetch_jwks(
        self, *, force_refresh: bool = False
    ) -> dict[str, dict[str, Any]]:
        if self._jwks_keys is None or force_refresh:
            logger.debug(
                "Fetching JWKS from Cognito: url=%s (force_refresh=%s)",
                self.jwks_url,
                force_refresh,
            )
            response = await self.http_client.get(self.jwks_url)
            response.raise_for_status()
            self._jwks_keys = {
                key["kid"]: key for key in response.json()["keys"] if "kid" in key
            }
        return self._jwks_keys

    async def verify_token(self, token: str) -> str:
        """Validate a Cognito JWT and return the authenticated user id (`sub`)."""
        app_client_id = self.settings.cognito_app_client_id
        if not app_client_id:
            raise CognitoJwtConfigurationException(
                "COGNITO_APP_CLIENT_ID is not configured"
            )

        logger.debug("Verifying Cognito JWT token...")
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            logger.debug(
                "JWT unverified header: kid=%s, alg=%s", kid, header.get("alg")
            )
            if not kid:
                raise CognitoJwtValidationException("Invalid token: missing kid header")

            jwks = await self._fetch_jwks()
            key_data = jwks.get(kid)
            if key_data is None:
                jwks = await self._fetch_jwks(force_refresh=True)
                key_data = jwks.get(kid)
            if key_data is None:
                raise CognitoJwtValidationException(
                    "Invalid token: signing key not found"
                )

            signing_key = PyJWK.from_dict(key_data)
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "require": ["exp", "sub", "token_use"],
                    "verify_aud": False,
                },
            )
        except CognitoJwtValidationException:
            raise
        except jwt.PyJWTError as exc:
            raise CognitoJwtValidationException(f"Invalid token: {exc}") from exc
        except httpx.HTTPError as exc:
            raise CognitoJwtValidationException(
                f"Unable to fetch Cognito JWKS: {exc}"
            ) from exc

        token_use = payload.get("token_use")
        if token_use == "id":
            if payload.get("aud") != app_client_id:
                raise CognitoJwtValidationException("Invalid token audience")
        elif token_use == "access":
            if payload.get("client_id") != app_client_id:
                raise CognitoJwtValidationException("Invalid token client_id")
        else:
            raise CognitoJwtValidationException("Invalid token_use claim")

        user_id = payload.get("sub")
        logger.debug(
            "JWT validation succeeded: sub=%s, token_use=%s, exp=%s",
            user_id,
            token_use,
            payload.get("exp"),
        )
        if not user_id:
            raise CognitoJwtValidationException("Invalid token: missing sub claim")

        return user_id
