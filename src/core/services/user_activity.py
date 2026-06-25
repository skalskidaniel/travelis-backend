from datetime import date, datetime, time, timezone
from datetime import timedelta

from aws_lambda_powertools import Logger

from core.models.user import User
from core.repositories.base import CellsRepository, UsersRepository
from core.services.activation import generate_required_cells

logger = Logger(child=True)


def seconds_until_next_utc_midnight(now: datetime | None = None) -> int:
    """Seconds remaining until the next 00:00 UTC. The Redis key TTL is anchored
    to UTC midnight, so a touch early in a day doesn't trigger a second write
    near day-end and vice versa.
    """
    now = now or datetime.now(timezone.utc)
    tomorrow = datetime.combine(
        date.fromordinal(now.date().toordinal() + 1),
        time.min,
        tzinfo=timezone.utc,
    )
    return max(int((tomorrow - now).total_seconds()), 1)


class UserActivityService:
    """Tracks user activity and deactivates cells for users idle beyond the threshold."""

    def __init__(
        self,
        users_repo: UsersRepository,
        cells_repo: CellsRepository,
        redis_client,
        inactivity_threshold_days: int,
    ) -> None:
        self.users_repo = users_repo
        self.cells_repo = cells_repo
        self.redis = redis_client
        self.inactivity_threshold_days = inactivity_threshold_days

    @staticmethod
    def _redis_key(user_id: str) -> str:
        return f"user:{user_id}:last_seen_daily"

    async def touch_daily(self, user_id: str) -> None:
        """First call per UTC day writes last_seen_date to DynamoDB; later calls are no-ops.

        Redis SET ... NX EX dedupes so at most one DynamoDB write hits per user per day.
        """
        today = date.today()
        ttl = seconds_until_next_utc_midnight()
        first_today = await self.redis.set(
            self._redis_key(user_id),
            today.isoformat(),
            ex=ttl,
            nx=True,
        )
        if not first_today:
            return
        try:
            await self.users_repo.touch_last_seen(user_id, today)
        except Exception as exc:
            logger.warning(
                f"Failed to persist last_seen_date for user {user_id}: {exc}"
            )

    async def ensure_active(self, user: User) -> bool:
        """Re-activate an inactive user by restoring their cell activations.

        Returns True iff a reactivation just happened (caller should schedule a re-match).
        """
        if user.is_active:
            return False
        await self.users_repo.clear_inactive([user.user_id])
        await self.cells_repo.activate_cells(generate_required_cells(user.preferences))
        logger.info(f"Reactivated cells for returning user {user.user_id}")
        return True

    async def sweep(self) -> dict:
        """Weekly: decrement cell activations for users idle beyond the threshold."""
        cutoff = date.today() - timedelta(days=self.inactivity_threshold_days)
        inactive_users = await self.users_repo.list_users_inactive_since(cutoff)
        if not inactive_users:
            logger.info("Inactivity sweep: no users to deactivate.")
            return {"users": 0, "cells": 0}

        cell_ids: list[str] = []
        for user in inactive_users:
            cells = generate_required_cells(user.preferences)
            cell_ids.extend(c.cell_id for c in cells if c.cell_id)

        if cell_ids:
            await self.cells_repo.decrement_activations(cell_ids)

        marked = await self.users_repo.mark_inactive(
            [u.user_id for u in inactive_users]
        )
        logger.info(
            f"Inactivity sweep: marked {marked} inactive users, "
            f"decremented {len(cell_ids)} cell activations."
        )
        return {"users": marked, "cells": len(cell_ids)}
