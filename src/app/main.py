import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.auth.controller import router as auth_router
from app.health.controller import router as health_router
from app.offers.controller import router as offers_router
from app.user.controller import router as user_router

app = FastAPI(title="TraveLis Backend API", version="2.0.0")

#TODO
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v2/auth")
app.include_router(health_router, prefix="/api/v2/health")
app.include_router(offers_router, prefix="/api/v2/offers")
app.include_router(user_router, prefix="/api/v2/user")

mangum_handler = Mangum(app, lifespan="off")  # TODO what is lifespan and why is it off?


def handler(event: dict, context) -> dict:
    """Dual-entry Lambda handler.

    Dispatches HTTP requests to FastAPI (via Mangum) and routes background
    jobs (EventBridge, Cognito triggers, Scheduler) to the jobs module.
    """
    is_http = "requestContext" in event or "httpMethod" in event or "rawPath" in event

    if is_http:
        return mangum_handler(event, context)

    # Non-HTTP events (EventBridge, Cognito, Scheduler)
    trigger_source = event.get("triggerSource")
    detail_type = event.get("detail-type")

    print(
        f"Received non-HTTP event: triggerSource={trigger_source}, detail_type={detail_type}"
    )
    return {
        "status": "success",
        "message": "Event received and logged (stub)",
        "event": event,
    }


if __name__ == "__main__":
    # Used for debugging purposes
    uvicorn.run(app, host="0.0.0.0", port=8000)
