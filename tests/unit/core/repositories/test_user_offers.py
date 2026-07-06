import pytest
from datetime import datetime

from core.repositories.user_offers import DynamoUserOffersRepository

pytestmark = pytest.mark.asyncio


async def test_user_offers_repo_lifecycle(user_offers_table):
    repo = DynamoUserOffersRepository(user_offers_table)

    user_id = "usr_123"
    offer_id = "off_456"
    cell_id = "cell_789"
    now = datetime(2026, 6, 17, 12, 0, 0)

    await repo.put(user_id, offer_id, cell_id, now)
    fetched = await repo.get(user_id, offer_id)
    assert fetched is not None
    assert fetched["user_id"] == user_id
    assert fetched["offer_id"] == offer_id
    assert fetched["cell_id"] == cell_id
    assert fetched["matched_at"] == now

    records = await repo.query_by_user(user_id)
    assert len(records) == 1
    assert records[0]["offer_id"] == offer_id

    await repo.delete(user_id, offer_id)
    assert await repo.get(user_id, offer_id) is None


async def test_user_offers_repo_batch(user_offers_table):
    repo = DynamoUserOffersRepository(user_offers_table)

    now = datetime(2026, 6, 17, 12, 0, 0)
    items = [
        {
            "user_id": "usr_1",
            "offer_id": "off_1",
            "cell_id": "cell_1",
            "matched_at": now,
        },
        {
            "user_id": "usr_1",
            "offer_id": "off_2",
            "cell_id": "cell_1",
            "matched_at": now,
        },
    ]

    await repo.put_batch(items)

    records = await repo.query_by_user("usr_1")
    assert len(records) == 2

    await repo.delete_batch([("usr_1", "off_1"), ("usr_1", "off_2")])
    records = await repo.query_by_user("usr_1")
    assert len(records) == 0
