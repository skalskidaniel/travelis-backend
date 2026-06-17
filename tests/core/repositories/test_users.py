import pytest
from datetime import datetime

from core.exceptions.repository import ItemNotFoundException
from core.models.user import (
    User,
    UserPreferences,
    PushSubscription,
    PushSubscriptionKeys,
)
from core.repositories.users import DynamoUsersRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def test_user():
    return User(
        user_id="usr_123",
        preferences=UserPreferences(
            countries=["GR", "IT"],
            adults=2,
            min_stars=3,
        ),
        push_enabled=False,
        push_subscription=None,
        created_at=datetime(2026, 6, 17, 12, 0, 0),
        updated_at=datetime(2026, 6, 17, 12, 0, 0),
    )


async def test_users_repo_lifecycle(users_table, test_user):
    repo = DynamoUsersRepository(users_table)

    await repo.put(test_user)
    fetched = await repo.get(test_user.user_id)
    assert fetched is not None
    assert fetched.user_id == test_user.user_id
    assert fetched.preferences.countries == ["GR", "IT"]
    assert fetched.preferences.adults == 2
    assert fetched.preferences.min_stars == 3
    assert fetched.push_enabled is False

    sub = PushSubscription(
        endpoint="https://push.example.com/sub/123",
        keys=PushSubscriptionKeys(p256dh="key_p256dh", auth="key_auth"),
    )
    await repo.update_push(test_user.user_id, enabled=True, subscription=sub)

    fetched = await repo.get(test_user.user_id)
    assert fetched.push_enabled is True
    assert fetched.push_subscription is not None
    assert fetched.push_subscription.endpoint == "https://push.example.com/sub/123"
    assert fetched.push_subscription.keys.auth == "key_auth"

    await repo.delete(test_user.user_id)
    assert await repo.get(test_user.user_id) is None


async def test_users_repo_update_push_raises_when_user_missing(users_table):
    repo = DynamoUsersRepository(users_table)

    with pytest.raises(ItemNotFoundException, match="User not found: missing-user"):
        await repo.update_push("missing-user", enabled=True, subscription=None)
