import logging
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from core.container import Container
from core.services.activation import generate_required_cells

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Cascade delete user, preferences, UserOffers, Redis keys, cell activations, and Cognito user."""
    user = await container.users_repo.get(user_id)

    if user is not None:
        # 1. Decrement cell activations
        try:
            cells = generate_required_cells(user.preferences)
            if cells:
                await container.cells_repo.decrement_activations(
                    [c.cell_id for c in cells]
                )
        except Exception as exc:
            logger.error(
                f"Error decrementing cell activations for deleted user {user_id}: {exc}"
            )

        # 2. Delete all UserOffers matching user_id
        try:
            user_offers = await container.user_offers_repo.query_by_user(user_id)
            if user_offers:
                keys = [(user_id, item["offer_id"]) for item in user_offers]
                await container.user_offers_repo.delete_batch(keys)
        except Exception as exc:
            logger.error(f"Error deleting UserOffers for deleted user {user_id}: {exc}")

        # 3. Clear user feed cache from Redis
        try:
            await container.feed_repo.clear_user(user_id)
        except Exception as exc:
            logger.error(
                f"Error clearing Redis cache for deleted user {user_id}: {exc}"
            )

        # 4. Delete user record from Users table
        try:
            await container.users_repo.delete(user_id)
        except Exception as exc:
            logger.error(f"Error deleting user record for {user_id}: {exc}")

    # 5. Delete Cognito user
    if container.settings.cognito_user_pool_id:
        try:
            await container.cognito_client.admin_delete_user(
                UserPoolId=container.settings.cognito_user_pool_id,
                Username=user_id,
            )
            logger.info(f"Successfully deleted Cognito user {user_id}")
        except Exception as exc:
            logger.error(f"Failed to delete Cognito user {user_id}: {exc}")
    else:
        logger.warning(
            "COGNITO_USER_POOL_ID not configured. Skipping Cognito user deletion."
        )
