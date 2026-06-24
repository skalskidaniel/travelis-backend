import pytest
from unittest.mock import AsyncMock
from botocore.exceptions import ClientError

from core.config import Settings
from core.exceptions.scheduler import (
    ScheduleCreateException,
    SchedulerNotConfiguredException,
    ScheduleUpdateException,
)
from core.services.scheduler import MATCH_DEBOUNCE_SECONDS, SchedulerService


@pytest.fixture
def mock_aws_arns(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv(
        "LAMBDA_FUNCTION_ARN",
        "arn:aws:lambda:eu-central-1:123456789012:function:travelis",
    )
    monkeypatch.setenv(
        "SCHEDULER_ROLE_ARN", "arn:aws:iam::123456789012:role/scheduler-role"
    )


@pytest.mark.asyncio
async def test_schedule_match_raises_when_client_missing(mock_aws_arns):
    settings = Settings()
    service = SchedulerService(scheduler_client=None, settings=settings)

    with pytest.raises(SchedulerNotConfiguredException):
        await service.schedule_match("user-123")


@pytest.mark.asyncio
async def test_schedule_match_raises_when_arns_missing(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.delenv("LAMBDA_FUNCTION_ARN", raising=False)
    monkeypatch.delenv("SCHEDULER_ROLE_ARN", raising=False)

    settings = Settings()
    settings.lambda_function_arn = None
    settings.scheduler_role_arn = None
    mock_client = AsyncMock()
    service = SchedulerService(scheduler_client=mock_client, settings=settings)

    with pytest.raises(SchedulerNotConfiguredException):
        await service.schedule_match("user-123")

    mock_client.update_schedule.assert_not_called()
    mock_client.create_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_match_update_success(mock_aws_arns):
    settings = Settings()
    mock_client = AsyncMock()
    service = SchedulerService(scheduler_client=mock_client, settings=settings)

    await service.schedule_match("user-123")
    mock_client.update_schedule.assert_called_once()
    mock_client.create_schedule.assert_not_called()

    kwargs = mock_client.update_schedule.call_args[1]
    assert kwargs["Name"] == "match-user-123"
    assert kwargs["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert kwargs["Target"]["Arn"] == settings.lambda_function_arn
    assert kwargs["Target"]["RoleArn"] == settings.scheduler_role_arn
    assert "user-123" in kwargs["Target"]["Input"]
    assert f"+ {MATCH_DEBOUNCE_SECONDS}" not in kwargs["ScheduleExpression"]


@pytest.mark.asyncio
async def test_schedule_match_create_fallback(mock_aws_arns):
    settings = Settings()
    mock_client = AsyncMock()
    error_response = {
        "Error": {"Code": "ResourceNotFoundException", "Message": "Schedule not found"}
    }
    mock_client.update_schedule.side_effect = ClientError(
        error_response, "UpdateSchedule"
    )

    service = SchedulerService(scheduler_client=mock_client, settings=settings)

    await service.schedule_match("user-123")
    mock_client.update_schedule.assert_called_once()
    mock_client.create_schedule.assert_called_once()

    kwargs = mock_client.create_schedule.call_args[1]
    assert kwargs["Name"] == "match-user-123"
    assert kwargs["Target"]["Arn"] == settings.lambda_function_arn


@pytest.mark.asyncio
async def test_schedule_match_raises_on_create_failure(mock_aws_arns):
    settings = Settings()
    mock_client = AsyncMock()
    not_found = {
        "Error": {"Code": "ResourceNotFoundException", "Message": "Schedule not found"}
    }
    mock_client.update_schedule.side_effect = ClientError(not_found, "UpdateSchedule")
    mock_client.create_schedule.side_effect = RuntimeError("create failed")

    service = SchedulerService(scheduler_client=mock_client, settings=settings)

    with pytest.raises(ScheduleCreateException):
        await service.schedule_match("user-123")


@pytest.mark.asyncio
async def test_schedule_match_raises_on_update_failure(mock_aws_arns):
    settings = Settings()
    mock_client = AsyncMock()
    mock_client.update_schedule.side_effect = RuntimeError("update failed")

    service = SchedulerService(scheduler_client=mock_client, settings=settings)

    with pytest.raises(ScheduleUpdateException):
        await service.schedule_match("user-123")
