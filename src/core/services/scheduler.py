import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from core.config import Settings
from core.exceptions.scheduler import (
    ScheduleCreateException,
    SchedulerNotConfiguredException,
    ScheduleUpdateException,
)

logger = logging.getLogger(__name__)

MATCH_DEBOUNCE_SECONDS = 15


class SchedulerService:
    """Manages EventBridge Scheduler one-time match tasks for users."""

    def __init__(self, scheduler_client: Any, settings: Settings) -> None:
        self.scheduler = scheduler_client
        self.settings = settings

    async def schedule_match(self, user_id: str) -> None:
        """Upsert a one-time schedule named `match-{user_id}` for 15 seconds from now.

        Coalescing: Overwrites the schedule fire time if it already exists, debouncing matching.
        """
        if self.scheduler is None:
            raise SchedulerNotConfiguredException(
                "EventBridge Scheduler client is not initialized"
            )

        lambda_arn = self.settings.lambda_function_arn
        role_arn = self.settings.scheduler_role_arn

        if not lambda_arn or not role_arn:
            raise SchedulerNotConfiguredException(
                "LAMBDA_FUNCTION_ARN or SCHEDULER_ROLE_ARN is not configured"
            )

        name = f"match-{user_id}"
        run_time = datetime.now(timezone.utc) + timedelta(
            seconds=MATCH_DEBOUNCE_SECONDS
        )
        expression = f"at({run_time.strftime('%Y-%m-%dT%H:%M:%S')})"

        target_payload = {
            "type": "match_user",
            "user_id": user_id,
        }

        target = {
            "Arn": lambda_arn,
            "RoleArn": role_arn,
            "Input": json.dumps(target_payload),
        }

        try:
            await self.scheduler.update_schedule(
                Name=name,
                ScheduleExpression=expression,
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode": "OFF"},
                Target=target,
                ActionAfterCompletion="DELETE",
            )
            logger.info(
                f"Successfully updated (debounced) match schedule for user: {user_id}"
            )
        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if (
                error_code == "ResourceNotFoundException"
                or "not found" in str(exc).lower()
            ):
                try:
                    await self.scheduler.create_schedule(
                        Name=name,
                        ScheduleExpression=expression,
                        ScheduleExpressionTimezone="UTC",
                        FlexibleTimeWindow={"Mode": "OFF"},
                        Target=target,
                        ActionAfterCompletion="DELETE",
                    )
                    logger.info(
                        f"Successfully created new match schedule for user: {user_id}"
                    )
                except Exception as create_exc:
                    raise ScheduleCreateException(
                        f"Failed to create match schedule for user {user_id}: {create_exc}"
                    ) from create_exc
            else:
                raise ScheduleUpdateException(
                    f"Failed to update match schedule for user {user_id}: {exc}"
                ) from exc
