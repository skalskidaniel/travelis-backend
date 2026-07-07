from datetime import datetime, timedelta, timezone

from aws_lambda_powertools import Logger

from core.models.user import User
from core.repositories.base import CellsRepository, UsersRepository
from core.services.activation import generate_required_cells

logger = Logger(child=True)


class UserActivityService:
    """Tracks user activity and deactivates cells for users idle beyond the threshold."""

    def __init__(
        self,
        users_repo: UsersRepository,
        cells_repo: CellsRepository,
        redis_client,
        inactivity_threshold_days: int,
        session_gap_minutes: int = 30,
    ) -> None:
        self.users_repo = users_repo
        self.cells_repo = cells_repo
        self.redis = redis_client
        self.inactivity_threshold_days = inactivity_threshold_days
        self.session_gap_minutes = session_gap_minutes

    @staticmethod
    def _redis_key(user_id: str) -> str:
        return f"user:{user_id}:session"

    async def touch(self, user_id: str) -> None:
        """Detect session boundaries and persist last_active_at / new_since.

        A sliding Redis key marks the current session. `SET ... EX ... GET`
        atomically refreshes the TTL and returns the previous value in one
        round trip: if a previous value existed, the user is still within the
        same session (idle gap not exceeded) and there's nothing to persist.
        If it's absent (expired or first-ever touch), a new session has just
        started: the user's prior `last_active_at` becomes the `new_since`
        boundary used to resolve "new" offers, and `last_active_at` advances
        to now.
        """
        now = datetime.now(timezone.utc)
        ttl = self.session_gap_minutes * 60
        previous = await self.redis.set(
            self._redis_key(user_id),
            now.isoformat(),
            ex=ttl,
            get=True,
        )
        if previous is not None:
            return

        try:
            user = await self.users_repo.get(user_id)
            if user is None:
                return
            await self.users_repo.record_session_start(
                user_id, new_since=user.last_active_at, last_active_at=now
            )
        except Exception as exc:
            logger.warning(f"Failed to persist session start for user {user_id}: {exc}")

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
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.inactivity_threshold_days
        )
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
