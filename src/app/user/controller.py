from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from aws_lambda_powertools import Logger

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.rate_limiter import RateLimiter
from app.user.schemas import (
    PushEnableRequest,
    UserPreferencesUpdate,
)
from core.container import Container
from core.exceptions.scheduler import SchedulerException
from core.models.user import (
    User,
    UserPreferences,
    PushSubscription,
    PushSubscriptionKeys,
)

logger = Logger(child=True)
router = APIRouter(tags=["User Preferences & Notifications"])


async def get_or_create_user(user_id: str, container: Container) -> User:
    """Gets the user from the database, or provisions a new user with default preferences if not found."""
    user: User | None = await container.users_repo.get(user_id)
    if user is None:
        user: User = User(user_id=user_id)
        await container.users_repo.put(user)
        await container.activation_service.update_cell_activations(
            new_prefs=user.preferences, old_prefs=None
        )
        try:
            await container.scheduler_service.schedule_match(user_id)
        except SchedulerException as exc:
            logger.warning(
                f"Failed to schedule match for new user {user_id} (ignoring): {exc}"
            )
    return user


@router.get(
    "/preferences",
    response_model=UserPreferences,
    summary="Get user preferences",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    responses={
        200: {
            "description": "Successfully retrieved user preferences (creates default preferences if the user is new)."
        },
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def get_preferences(
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Retrieve the current user preferences (lazy provisioning if not exists)."""
    user: User = await get_or_create_user(user_id, container)
    return user.preferences


@router.patch(
    "/preferences",
    response_model=UserPreferences,
    summary="Update user preferences",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    responses={
        200: {
            "description": "Successfully updated preferences, synchronized cells, and scheduled matching."
        },
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def update_preferences(
    updates: UserPreferencesUpdate,
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Partially update user preferences, sync cell activations, and schedule matching."""
    user: User = await get_or_create_user(user_id, container)
    old_prefs: UserPreferences = user.preferences

    updated_dict = user.preferences.model_dump()
    for field, val in updates.model_dump(exclude_unset=True).items():
        updated_dict[field] = val

    new_prefs: UserPreferences = UserPreferences(**updated_dict)
    user.preferences = new_prefs
    user.updated_at = datetime.now(timezone.utc)

    await container.users_repo.put(user)

    await container.activation_service.update_cell_activations(
        new_prefs=new_prefs, old_prefs=old_prefs
    )

    try:
        await container.scheduler_service.schedule_match(user_id)
    except SchedulerException as exc:
        logger.warning(
            f"Failed to schedule match after preference update for user {user_id} (ignoring): {exc}"
        )

    return user.preferences


@router.post(
    "/push/enable",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Enable web push notifications",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    responses={
        204: {
            "description": "Successfully registered or updated Web Push subscription details."
        },
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def enable_push(
    req: PushEnableRequest,
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Register or update a Web Push subscription details for the user."""
    await get_or_create_user(user_id, container)

    sub: PushSubscription = PushSubscription(
        endpoint=req.subscription.endpoint,
        keys=PushSubscriptionKeys(
            p256dh=req.subscription.keys.p256dh,
            auth=req.subscription.keys.auth,
        ),
    )

    await container.users_repo.update_push(user_id, enabled=True, subscription=sub)


@router.post(
    "/push/disable",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable web push notifications",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    responses={
        204: {
            "description": "Successfully unregistered or disabled Web Push notifications."
        },
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def disable_push(
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Disable Web Push notifications for the user."""
    await get_or_create_user(user_id, container)
    await container.users_repo.update_push(user_id, enabled=False, subscription=None)
