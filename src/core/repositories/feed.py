from typing import Any

from core.repositories.base import FeedRepository


class RedisFeedRepository(FeedRepository):
    """Redis implementation of the FeedRepository."""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def get_feed_version(self, user_id: str) -> int:
        version = await self.redis.get(f"user:{user_id}:feed_version")
        return int(version) if version else 0

    async def increment_feed_version(self, user_id: str) -> int:
        version = await self.redis.incr(f"user:{user_id}:feed_version")
        return int(version)

    async def get_or_build_sort_zset(
        self, user_id: str, field: str, order: str, version: int
    ) -> bool:
        key = f"user:{user_id}:sort:{field}:{order}:v{version}"
        exists = await self.redis.exists(key)
        return bool(exists)

    async def add_to_sort_zset(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        members: list[tuple[str, float]],
    ) -> None:
        if not members:
            return

        key = f"user:{user_id}:sort:{field}:{order}:v{version}"
        mapping = {member: score for member, score in members}

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.zadd(key, mapping)
            await pipe.expire(key, 86400)  # 24 hours TTL
            await pipe.execute()

    async def get_page(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        offset: int,
        limit: int,
    ) -> list[tuple[str, str]]:
        key = f"user:{user_id}:sort:{field}:{order}:v{version}"
        start = offset
        end = offset + limit - 1
        desc = order == "desc"

        result = await self.redis.zrange(key, start, end, desc=desc)
        parsed = []
        for r in result:
            val = r.decode("utf-8") if isinstance(r, bytes) else r
            if ":" in val:
                parts = val.split(":", 1)
                parsed.append((parts[0], parts[1]))
            else:
                parsed.append((val, ""))
        return parsed

    async def get_size(
        self, user_id: str, field: str, order: str, version: int
    ) -> int:
        key = f"user:{user_id}:sort:{field}:{order}:v{version}"
        return await self.redis.zcard(key)

    async def clear_user(self, user_id: str) -> None:
        pattern = f"user:{user_id}:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)


stream = None
