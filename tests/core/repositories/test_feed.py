import pytest

from core.repositories.feed import RedisFeedRepository

pytestmark = pytest.mark.asyncio


async def test_feed_repo_version(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_123"
    assert await repo.get_feed_version(user_id) == 0

    new_ver = await repo.increment_feed_version(user_id)
    assert new_ver == 1
    assert await repo.get_feed_version(user_id) == 1

    new_ver = await repo.increment_feed_version(user_id)
    assert new_ver == 2
    assert await repo.get_feed_version(user_id) == 2


async def test_feed_repo_zset(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_123"
    field = "price"

    assert await repo.get_or_build_sort_zset(user_id, field, "desc", 1) is False

    members = [
        ("offer_1", 1000.5),
        ("offer_2", 500.2),
        ("offer_3", 1500.7),
    ]
    await repo.add_to_sort_zset(user_id, field, "desc", 1, members)

    assert await repo.get_or_build_sort_zset(user_id, field, "desc", 1) is True

    page_desc = await repo.get_page(user_id, field, "desc", 1, offset=0, limit=10)
    assert page_desc == ["offer_3", "offer_1", "offer_2"]

    page_desc_offset = await repo.get_page(user_id, field, "desc", 1, offset=1, limit=1)
    assert page_desc_offset == ["offer_1"]

    await repo.add_to_sort_zset(user_id, field, "asc", 1, members)
    page_asc = await repo.get_page(user_id, field, "asc", 1, offset=0, limit=10)
    assert page_asc == ["offer_2", "offer_1", "offer_3"]


async def test_feed_repo_clear_user(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_123"
    await repo.increment_feed_version(user_id)
    await repo.add_to_sort_zset(user_id, "price", "desc", 1, [("offer_1", 100.0)])

    assert await redis_client.exists(f"user:{user_id}:feed_version")
    assert await redis_client.exists(f"user:{user_id}:sort:price:desc:v1")

    await repo.clear_user(user_id)

    assert not await redis_client.exists(f"user:{user_id}:feed_version")
    assert not await redis_client.exists(f"user:{user_id}:sort:price:desc:v1")
