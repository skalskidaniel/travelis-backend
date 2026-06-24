import asyncio
from contextlib import asynccontextmanager

from aws_lambda_powertools import Logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.auth.controller import router as auth_router
from app.exceptions import (
    AccountDeletionException,
    AuthenticationException,
    MatchSchedulingException,
    RetryableServiceException,
    ServiceConfigurationException,
    UnknownJobEventException,
)
from app.health.controller import router as health_router
from app.jobs.availability import run_availability_job
from app.jobs.coordinator import run_scrape_job
from app.offers.controller import router as offers_router
from app.user.controller import router as user_router
from core.container import container
from core.exceptions.scheduler import SchedulerException

logger = Logger(
    service="travelis-backend",
    level=container.settings.powertools_log_level,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await container.initialize()
    yield
    await container.cleanup()


API_DESCRIPTION = """
This API powers the TraveLis holiday search assistant, providing personalized travel offer matching feeds, push notification preferences, and search synchronization.

### Key Features
* **Offers Feed**: Access a personalized, ranked feed of travel packages tailored to your holiday preferences.
* **User Preferences**: Save and modify target destinations, departure airports, dates, occupants, and hotel requirements.
* **Web Push Notifications**: Subscribe/unsubscribe to receive push alerts when new highly-attractive matched offers are compiled.
* **Health & Auth**: Built-in OAuth2/JWT security backed by AWS Cognito and lightweight health telemetry.

### Authentication
Most endpoints require a valid AWS Cognito ID Token transmitted in the `Authorization` header as a Bearer token:
```
Authorization: Bearer <cognito_jwt_token>
```
"""

TAGS_METADATA = [
    {
        "name": "Authentication",
        "description": "Operations related to authentication and user account deletion.",
    },
    {
        "name": "Health Check",
        "description": "Telemetry and system health checks.",
    },
    {
        "name": "Offers Feed",
        "description": "Endpoints for retrieving personal matched offers feed and shared offer details.",
    },
    {
        "name": "User Preferences & Notifications",
        "description": "Endpoints to manage search criteria, occupant counts, and configure Web Push alerts.",
    },
]

is_prod = container.settings.environment == "prod"

app = FastAPI(
    title="TraveLis Backend API",
    version="2.0.0",
    description=API_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)


@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(
    request: Request, exc: AuthenticationException
) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(RetryableServiceException)
async def retryable_service_exception_handler(
    request: Request, exc: RetryableServiceException
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "retryable": True},
    )


@app.exception_handler(SchedulerException)
async def scheduler_exception_handler(
    request: Request, exc: SchedulerException
) -> JSONResponse:
    logger.error(f"Scheduler exception occurred: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable", "retryable": True},
    )


@app.exception_handler(ServiceConfigurationException)
async def service_configuration_exception_handler(
    request: Request, exc: ServiceConfigurationException
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(AccountDeletionException)
async def account_deletion_exception_handler(
    request: Request, exc: AccountDeletionException
) -> JSONResponse:
    logger.error(f"Account deletion failed: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(auth_router, prefix="/api/v2/auth")
app.include_router(health_router, prefix="/api/v2/health")
app.include_router(offers_router, prefix="/api/v2/offers")
app.include_router(user_router, prefix="/api/v2/user")

mangum_handler = Mangum(app, lifespan="off")  # must remain "off" to work with mangum


async def handle_non_http(event: dict, context) -> dict:
    """Async router for EventBridge, Cognito, and Scheduler events."""
    await container.initialize()

    trigger_source = event.get("triggerSource")
    event_type = event.get("type")

    # A. Cognito post-confirmation trigger
    if trigger_source and trigger_source.startswith("PostConfirmation"):
        user_id = (
            event.get("request", {})
            .get("userAttributes", {})
            .get("sub")
            or event.get("userName")
        )
        if user_id:
            from app.user.controller import get_or_create_user

            await get_or_create_user(user_id, container)
            logger.info(
                "Cognito PostConfirmation: successfully provisioned user %s", user_id
            )
        return event  # Cognito triggers must echo the event

    # B. EventBridge Scheduler debounced match job
    elif event_type == "match_user":
        user_id = event.get("user_id")
        if user_id:
            logger.info("EventBridge Scheduler: matching user %s", user_id)
            feed_changed = await container.matching_service.match_user_offers(user_id)
            return {
                "status": "success",
                "message": f"Matching completed for user {user_id}",
                "feed_changed": feed_changed,
            }
        else:
            raise MatchSchedulingException("Missing user_id for match_user event")

    # C. EventBridge scrape coordinator job
    elif event_type == "scrape_offers":
        logger.info("EventBridge: Starting scrape_offers job")

        results = await run_scrape_job(container, context, payload=event)
        return {
            "status": "success",
            "message": "Scraper coordinator job completed",
            "results": results,
        }

    # D. EventBridge availability check job
    elif event_type == "check_availability":
        logger.info("EventBridge: Starting check_availability job")

        results = await run_availability_job(container, context)
        return {
            "status": "success",
            "message": "Availability check job completed",
            "results": results,
        }

    # E. Unrecognized non-HTTP events
    else:
        logger.error(
            "Unrecognized non-HTTP event: triggerSource=%s, type=%s",
            trigger_source,
            event_type,
        )
        raise UnknownJobEventException(
            f"Unrecognized job event (triggerSource={trigger_source!r}, type={event_type!r})"
        )


@logger.inject_lambda_context(clear_state=True)
def handler(event: dict, context) -> dict:
    """Dual-entry Lambda handler.

    Dispatches HTTP requests to FastAPI (via Mangum) and routes background
    jobs (EventBridge, Cognito triggers, Scheduler) to the jobs module.
    """
    is_http = "requestContext" in event or "httpMethod" in event or "rawPath" in event

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if is_http:
        return mangum_handler(event, context)

    return loop.run_until_complete(handle_non_http(event, context))


if __name__ == "__main__":
    # Used for debugging purposes
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
