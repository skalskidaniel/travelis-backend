from core.exceptions.common import CoreException


class SchedulerException(CoreException):
    """Base exception for EventBridge Scheduler failures."""

    pass


class SchedulerNotConfiguredException(SchedulerException):
    """Raised when scheduler client or required ARNs are missing."""

    pass


class ScheduleUpdateException(SchedulerException):
    """Raised when updating an existing match schedule fails."""

    pass


class ScheduleCreateException(SchedulerException):
    """Raised when creating a match schedule fails."""

    pass
