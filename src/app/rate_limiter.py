import jwt
from aws_lambda_powertools import Logger
from fastapi import Depends, HTTPException, Request, status

from app.dependencies import get_container
from core.container import Container

logger = Logger(child=True)


class RateLimiter:
    """FastAPI dependency for rate limiting requests using Redis.

    Fails open gracefully if Redis is unavailable or experiences connection issues.
    """

    def __init__(self, times: int, seconds: int, key_prefix: str = "rate_limit"):
        self.times = times
        self.seconds = seconds
        self.key_prefix = key_prefix

    async def __call__(
        self, request: Request, container: Container = Depends(get_container)
    ):
        # 1. Check if rate limiting is enabled globally
        if not container.settings.rate_limiting_enabled:
            return

        # 2. Check if redis client is available
        if not container.redis_client:
            logger.warning("Redis client not initialized. Bypassing rate limiter.")
            return

        # 3. Resolve request identifier
        identifier = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                # Decode token without signature verification to extract "sub"
                # (Actual authentication/verification is still handled by get_current_user)
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub")
                if user_id:
                    identifier = f"user:{user_id}"
            except Exception as exc:
                logger.debug(
                    f"Failed to decode Authorization header for rate limiting: {exc}"
                )

        if not identifier:
            ip = request.client.host if request.client else "unknown"
            identifier = f"ip:{ip}"

        # 4. Construct Redis rate limit key
        path = request.url.path
        key = f"{self.key_prefix}:{identifier}:{path}"

        # 5. Enforce limit
        try:
            pipe = container.redis_client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            current_count, ttl = await pipe.execute()

            if current_count == 1 or ttl == -1:
                await container.redis_client.expire(key, self.seconds)
                ttl = self.seconds

            if current_count > self.times:
                headers = {"Retry-After": str(max(0, ttl))}
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers=headers,
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Fail-open: log warning and let request proceed
            logger.warning(
                f"Redis rate limiter encountered error: {exc}. Failing open and permitting request."
            )
            return
