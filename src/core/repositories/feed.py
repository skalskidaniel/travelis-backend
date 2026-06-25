from typing import Any

from core.repositories.base import FeedRepository


def _sort_zset_key(
    user_id: str, field: str, order: str, version: int, filter_mode: str
) -> str:
    return (
        f"user:{user_id}:sort:{field}:{order}:filter:{filter_mode}:v{version}"
    )


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
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        filter_mode: str = "all",
    ) -> bool:
        key = _sort_zset_key(user_id, field, order, version, filter_mode)
        exists = await self.redis.exists(key)
        return bool(exists)

    async def add_to_sort_zset(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        members: list[tuple[str, float]],
        filter_mode: str = "all",
    ) -> None:
        if not members:
            return

        key = _sort_zset_key(user_id, field, order, version, filter_mode)
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
        filter_mode: str = "all",
    ) -> list[tuple[str, str]]:
        key = _sort_zset_key(user_id, field, order, version, filter_mode)
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
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        filter_mode: str = "all",
    ) -> int:
        key = _sort_zset_key(user_id, field, order, version, filter_mode)
        return await self.redis.zcard(key)

    async def clear_user(self, user_id: str) -> None:
        pattern = f"user:{user_id}:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)


stream = None
