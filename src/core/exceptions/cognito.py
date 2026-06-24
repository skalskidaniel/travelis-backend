from core.exceptions.common import CoreException


class CognitoJwtException(CoreException):
    """Base exception for Cognito JWT verification failures."""

    pass


class CognitoJwtValidationException(CognitoJwtException):
    """Raised when a Cognito JWT fails validation."""

    pass


class CognitoJwtConfigurationException(CognitoJwtException):
    """Raised when Cognito JWT verification is misconfigured."""

    pass
