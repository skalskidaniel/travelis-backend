from fastapi import Depends

from core.container import container, Container
from core.repositories.base import (
    UsersRepository,
    CellsRepository,
    OffersRepository,
    UserOffersRepository,
    FeedRepository,
)
from core.services.activation import ActivationService
from core.services.matching import MatchingService
from core.services.scheduler import SchedulerService


async def get_container() -> Container:
    """Dependency provider that lazily initializes the container if needed."""
    await container.initialize()
    return container


async def get_users_repo(c: Container = Depends(get_container)) -> UsersRepository:
    return c.users_repo


async def get_cells_repo(c: Container = Depends(get_container)) -> CellsRepository:
    return c.cells_repo


async def get_offers_repo(c: Container = Depends(get_container)) -> OffersRepository:
    return c.offers_repo


async def get_user_offers_repo(
    c: Container = Depends(get_container),
) -> UserOffersRepository:
    return c.user_offers_repo


async def get_feed_repo(c: Container = Depends(get_container)) -> FeedRepository:
    return c.feed_repo


async def get_activation_service(
    c: Container = Depends(get_container),
) -> ActivationService:
    return c.activation_service


async def get_matching_service(
    c: Container = Depends(get_container),
) -> MatchingService:
    return c.matching_service


async def get_scheduler_service(
    c: Container = Depends(get_container),
) -> SchedulerService:
    return c.scheduler_service
