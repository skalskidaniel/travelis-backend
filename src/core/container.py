from contextlib import AsyncExitStack
from typing import Any
import aioboto3
import httpx
from redis.asyncio import Redis

from core.config import Settings
from core.repositories.cells import DynamoCellsRepository
from core.repositories.offers import DynamoOffersRepository
from core.repositories.users import DynamoUsersRepository
from core.repositories.user_offers import DynamoUserOffersRepository
from core.repositories.feed import RedisFeedRepository


class Container:
    """Composition root for managing application dependencies and resources lifecycle."""

    def __init__(self) -> None:
        self.settings = Settings()
        self.exit_stack: AsyncExitStack | None = None
        self._loop: Any = None

        # Clients / Resources
        self.dynamodb_resource: Any = None
        self.redis_client: Redis | None = None
        self.scheduler_client: Any = None
        self.cognito_client: Any = None
        self.lambda_client: Any = None
        self.http_client: httpx.AsyncClient | None = None  # pyright: ignore[reportUndefinedVariable]

        # Providers
        self.tui_provider: Any = None
        self.wakacje_provider: Any = None

        # Repositories
        self.users_repo: DynamoUsersRepository | None = None
        self.cells_repo: DynamoCellsRepository | None = None
        self.offers_repo: DynamoOffersRepository | None = None
        self.user_offers_repo: DynamoUserOffersRepository | None = None
        self.feed_repo: RedisFeedRepository | None = None

        # Services
        self.activation_service: Any = None
        self.matching_service: Any = None
        self.notifications_service: Any = None
        self.scheduler_service: Any = None
        self.cognito_jwt_verifier: Any = None
        self.user_activity_service: Any = None

    async def initialize(self) -> None:
        """Initialize all shared resources once per cold start."""
        import asyncio

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self.exit_stack is not None:
            if (
                self._loop == current_loop
                and current_loop is not None
                and not current_loop.is_closed()
            ):
                return
            await self.cleanup()

        self._loop = current_loop

        import httpx
        from core.providers.tui.main import TuiProvider
        from core.providers.wakacjepl.main import WakacjePlProvider

        self.exit_stack = AsyncExitStack()

        self.http_client = await self.exit_stack.enter_async_context(
            httpx.AsyncClient(timeout=15.0)
        )
        self.tui_provider = TuiProvider(self.http_client)
        self.wakacje_provider = WakacjePlProvider(self.http_client)

        session = aioboto3.Session(profile_name=self.settings.aws_profile)
        self.dynamodb_resource = await self.exit_stack.enter_async_context(
            session.resource("dynamodb", region_name=self.settings.aws_region)
        )
        self.scheduler_client = await self.exit_stack.enter_async_context(
            session.client("scheduler", region_name=self.settings.aws_region)
        )
        self.cognito_client = await self.exit_stack.enter_async_context(
            session.client("cognito-idp", region_name=self.settings.aws_region)
        )
        self.lambda_client = await self.exit_stack.enter_async_context(
            session.client("lambda", region_name=self.settings.aws_region)
        )

        users_table = await self.dynamodb_resource.Table(self.settings.db.users_table)
        cells_table = await self.dynamodb_resource.Table(self.settings.db.cells_table)
        offers_table = await self.dynamodb_resource.Table(self.settings.db.offers_table)
        user_offers_table = await self.dynamodb_resource.Table(
            self.settings.db.user_offers_table
        )

        self.users_repo = DynamoUsersRepository(users_table)
        self.cells_repo = DynamoCellsRepository(cells_table)
        self.offers_repo = DynamoOffersRepository(offers_table)
        self.user_offers_repo = DynamoUserOffersRepository(user_offers_table)

        self.redis_client = Redis.from_url(
            self.settings.redis_url, decode_responses=True
        )
        self.exit_stack.push_async_callback(self.redis_client.aclose)
        self.feed_repo = RedisFeedRepository(self.redis_client)

        from core.services.activation import ActivationService
        from core.services.notifications import NotificationsService
        from core.services.matching import MatchingService
        from core.services.scheduler import SchedulerService
        from core.services.cognito_jwt import CognitoJwtVerifier
        from core.services.user_activity import UserActivityService

        vapid_private_key = self.settings.vapid_private_key
        if self.settings.vapid_private_key_secret_arn:
            secrets_client = await self.exit_stack.enter_async_context(
                session.client("secretsmanager", region_name=self.settings.aws_region)
            )
            secret_response = await secrets_client.get_secret_value(
                SecretId=self.settings.vapid_private_key_secret_arn
            )
            vapid_private_key = secret_response["SecretString"]

        self.activation_service = ActivationService(
            cells_repo=self.cells_repo,
        )
        self.notifications_service = NotificationsService(
            vapid_private_key=vapid_private_key,
            vapid_public_key=self.settings.push.vapid_public_key,
        )
        self.matching_service = MatchingService(
            users_repo=self.users_repo,
            offers_repo=self.offers_repo,
            user_offers_repo=self.user_offers_repo,
            feed_repo=self.feed_repo,
            notifications_service=self.notifications_service,
            activation_service=self.activation_service,
        )
        self.scheduler_service = SchedulerService(
            scheduler_client=self.scheduler_client,
            settings=self.settings,
        )
        self.cognito_jwt_verifier = CognitoJwtVerifier(
            settings=self.settings,
            http_client=self.http_client,
        )
        self.user_activity_service = UserActivityService(
            users_repo=self.users_repo,
            cells_repo=self.cells_repo,
            redis_client=self.redis_client,
            inactivity_threshold_days=self.settings.inactivity_threshold_days,
        )

    async def cleanup(self) -> None:
        """Close and release all resources cleanly."""
        if self.exit_stack is not None:
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass
            self.exit_stack = None
            self.dynamodb_resource = None
            self.redis_client = None
            self.scheduler_client = None
            self.cognito_client = None
            self.lambda_client = None
            self.http_client = None
            self.tui_provider = None
            self.wakacje_provider = None
            self.users_repo = None
            self.cells_repo = None
            self.offers_repo = None
            self.user_offers_repo = None
            self.feed_repo = None
            self.activation_service = None
            self.matching_service = None
            self.notifications_service = None
            self.scheduler_service = None
            self.cognito_jwt_verifier = None
            self.user_activity_service = None
            self._loop = None


container = Container()
