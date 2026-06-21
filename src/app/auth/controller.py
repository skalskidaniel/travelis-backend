import logging
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.exceptions import AccountDeletionException
from core.container import Container
from core.services.activation import generate_required_cells

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user account",
    responses={
        204: {
            "description": "Account and all associated preferences, matched feed, and web push subscriptions were successfully deleted."
        },
        401: {"description": "Unauthorized - Invalid or missing Cognito JWT token."},
        500: {
            "description": "Internal Server Error - Failed to delete account resources."
        },
    },
)
async def delete_account(
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Cascade delete user, preferences, UserOffers, Redis keys, cell activations, and Cognito user."""
    user = await container.users_repo.get(user_id)

    if user is not None:
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
            raise AccountDeletionException(
                "Failed to decrement cell activations during account deletion"
            ) from exc

        try:
            user_offers = await container.user_offers_repo.query_by_user(user_id)
            if user_offers:
                keys = [(user_id, item["offer_id"]) for item in user_offers]
                await container.user_offers_repo.delete_batch(keys)
        except Exception as exc:
            logger.error(f"Error deleting UserOffers for deleted user {user_id}: {exc}")
            raise AccountDeletionException(
                "Failed to delete user offers during account deletion"
            ) from exc

        try:
            await container.feed_repo.clear_user(user_id)
        except Exception as exc:
            logger.error(
                f"Error clearing Redis cache for deleted user {user_id}: {exc}"
            )
            raise AccountDeletionException(
                "Failed to clear user feed cache during account deletion"
            ) from exc

        try:
            await container.users_repo.delete(user_id)
        except Exception as exc:
            logger.error(f"Error deleting user record for {user_id}: {exc}")
            raise AccountDeletionException(
                "Failed to delete user record during account deletion"
            ) from exc

    if container.settings.cognito_user_pool_id:
        try:
            await container.cognito_client.admin_delete_user(
                UserPoolId=container.settings.cognito_user_pool_id,
                Username=user_id,
            )
            logger.info(f"Successfully deleted Cognito user {user_id}")
        except Exception as exc:
            logger.error(f"Failed to delete Cognito user {user_id}: {exc}")
            raise AccountDeletionException(
                "Failed to delete Cognito user during account deletion"
            ) from exc
    else:
        logger.warning(
            "COGNITO_USER_POOL_ID not configured. Skipping Cognito user deletion."
        )
