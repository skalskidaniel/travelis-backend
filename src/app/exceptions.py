class AppException(Exception):
    """Base exception for app-layer HTTP-facing errors."""

    pass


class AuthenticationException(AppException):
    """Raised when JWT validation or authentication fails."""

    pass


class RetryableServiceException(AppException):
    """Raised when a transient infrastructure failure should be retried by the client."""

    pass


class AccountDeletionException(RetryableServiceException):
    """Raised when account deletion cannot complete safely."""

    pass


class MatchSchedulingException(RetryableServiceException):
    """Raised when debounced match scheduling fails."""

    pass


class ServiceConfigurationException(AppException):
    """Raised when required application configuration is missing or invalid."""

    pass
