from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies import get_container
from app.exceptions import AuthenticationException, ServiceConfigurationException
from core.container import Container
from core.exceptions.cognito import (
    CognitoJwtConfigurationException,
    CognitoJwtValidationException,
)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    container: Container = Depends(get_container),
) -> str:
    """Extract and validate the Cognito JWT from the Authorization header."""
    token = credentials.credentials
    try:
        user_id = await container.cognito_jwt_verifier.verify_token(token)
    except CognitoJwtConfigurationException as exc:
        raise ServiceConfigurationException(str(exc)) from exc
    except CognitoJwtValidationException as exc:
        raise AuthenticationException(str(exc)) from exc

    if container.user_activity_service is not None:
        import asyncio

        asyncio.create_task(container.user_activity_service.touch(user_id))

    return user_id
