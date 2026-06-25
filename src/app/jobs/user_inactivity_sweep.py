from aws_lambda_powertools import Logger

from core.container import Container

logger = Logger(child=True)


async def run_user_inactivity_sweep(
    container: Container, context=None, payload=None
) -> dict:
    """Weekly cron: decrement cell activations for users idle beyond the inactivity threshold.

    Cheap, idempotent — safe to run more often than weekly.
    """
    logger.info("Starting user inactivity sweep.")
    stats = await container.user_activity_service.sweep()
    logger.info(f"User inactivity sweep completed: {stats}")
    return stats
