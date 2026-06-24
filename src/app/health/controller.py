from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.dependencies import get_container
from core.container import Container

router = APIRouter(tags=["Health Check"])


@router.get("", summary="Get system health status")
async def health_check(container: Container = Depends(get_container)):
    """Returns operational status including Redis and DynamoDB connectivity."""
    checks: dict[str, str] = {}
    healthy = True

    if container.redis_client is None:
        checks["redis"] = "unavailable"
        healthy = False
    else:
        try:
            await container.redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
            healthy = False

    if container.users_repo is None:
        checks["dynamodb"] = "unavailable"
        healthy = False
    else:
        try:
            await container.users_repo.table.meta.client.describe_table(
                TableName=container.settings.users_table
            )
            checks["dynamodb"] = "ok"
        except Exception:
            checks["dynamodb"] = "error"
            healthy = False

    body = {"status": "ok" if healthy else "unhealthy", "checks": checks}
    if healthy:
        return body
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
