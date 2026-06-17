from core.exceptions.common import CoreException


class RepositoryException(CoreException):
    """Base exception for all repository failures."""

    pass


class ItemNotFoundException(RepositoryException):
    """Raised when an item is not found."""

    pass


class ConditionalCheckFailedException(RepositoryException):
    """Raised when a DynamoDB conditional write fails."""

    pass


class WriteException(RepositoryException):
    """Raised when a batch write or delete operation fails."""

    pass
