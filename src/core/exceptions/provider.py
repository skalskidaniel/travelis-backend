from core.exceptions.common import CoreException


class ProviderException(CoreException):
    """Base exception for all provider/adapter-related errors."""

    pass


class CountryNotFoundException(ProviderException):
    """Raised when a country code is not supported or found by a provider."""

    pass


class BoardTypeNotSupportedException(ProviderException):
    """Raised when a board type is not supported or mapped by a provider."""

    pass


class MinStarsNotSupportedException(ProviderException):
    """Raised when a minimum star rating is not supported or mapped by a provider."""

    pass


class InvalidOfferMetadataException(ProviderException):
    """Raised when offer metadata required for a provider operation is missing or invalid."""

    pass


class PastDatesException(ProviderException):
    """Raised when both search bounds (departure_from and departure_to) are in the past."""

    pass


class DateMismatchException(ProviderException):
    """Raised when the departure / start date is after the return / end date."""

    pass


class DurationMismatchException(ProviderException):
    """Raised when the duration does not match return_date - departure_date"""

    pass


class ProviderAPIException(ProviderException):
    """Raised when a provider's API call fails or returns an invalid/unexpected response."""

    pass


class ProviderTimeoutException(ProviderAPIException):
    """Raised when a provider API call times out."""

    pass


class TooManyRequestsException(ProviderAPIException):
    """Raised when the response status code is 429."""
    
    pass