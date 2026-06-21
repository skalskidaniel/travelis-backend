from fastapi import APIRouter

router = APIRouter(tags=["Health Check"])


@router.get("", summary="Get system health status")
async def health_check():
    """Returns the current operational status of the service."""
    return {"status": "ok"}
