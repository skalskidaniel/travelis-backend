import os
import pytest
import pytest_asyncio
import aioboto3
from decimal import Decimal
from datetime import datetime, date, timezone

from core.models.cell import MarketCell
from core.models.common import BoardType
from core.models.offer import Offer, OfferMetadata, TuiMetadata, ProviderName
from core.models.user import (
    User,
    UserPreferences,
    PushSubscription,
    PushSubscriptionKeys,
)
from core.repositories.cells import DynamoCellsRepository
from core.repositories.offers import DynamoOffersRepository
from core.repositories.users import DynamoUsersRepository
from core.repositories.user_offers import DynamoUserOffersRepository
import redis.asyncio as aioredis
from core.repositories.feed import RedisFeedRepository

pytestmark = pytest.mark.asyncio

ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")


@pytest_asyncio.fixture(scope="function")
async def dynamodb_resource():
    os.environ["AWS_ACCESS_KEY_ID"] = "local"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "local"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    os.environ.pop("AWS_SESSION_TOKEN", None)
    os.environ.pop("AWS_SECURITY_TOKEN", None)
    os.environ.pop("AWS_PROFILE", None)

    session = aioboto3.Session(
        aws_access_key_id="local",
        aws_secret_access_key="local",
        region_name="us-east-1",
    )
    async with session.resource(
        "dynamodb", endpoint_url=ENDPOINT_URL, region_name="us-east-1"
    ) as resource:
        yield resource


@pytest_asyncio.fixture(scope="function")
async def cells_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="MarketCells_Integration",
        KeySchema=[{"AttributeName": "cell_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "cell_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    await table.wait_until_exists()
    yield table
    await table.delete()
    await table.wait_until_not_exists()


@pytest_asyncio.fixture(scope="function")
async def offers_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="Offers_Integration",
        KeySchema=[
            {"AttributeName": "cell_id", "KeyType": "HASH"},
            {"AttributeName": "offer_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "cell_id", "AttributeType": "S"},
            {"AttributeName": "offer_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    await table.wait_until_exists()
    yield table
    await table.delete()
    await table.wait_until_not_exists()


@pytest_asyncio.fixture(scope="function")
async def users_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="Users_Integration",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    await table.wait_until_exists()
    yield table
    await table.delete()
    await table.wait_until_not_exists()


@pytest_asyncio.fixture(scope="function")
async def user_offers_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="UserOffers_Integration",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "offer_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "offer_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    await table.wait_until_exists()
    yield table
    await table.delete()
    await table.wait_until_not_exists()


# --- Cells Repository Integration Tests ---


@pytest.mark.asyncio
async def test_cells_repo_integration_lifecycle(cells_table):
    repo = DynamoCellsRepository(cells_table)

    cell = MarketCell(
        country="MX",
        month="2026-07",
        min_stars=4,
        board=BoardType.ALL_INCLUSIVE,
        adults=2,
        children=0,
        activation_count=1,
    )

    await repo.put(cell)
    fetched = await repo.get(cell.cell_id)
    assert fetched is not None
    assert fetched.cell_id == cell.cell_id
    assert fetched.country == "MX"
    assert fetched.activation_count == 1

    all_cells: list[MarketCell] = await repo.scan()
    assert len(all_cells) == 1
    assert all_cells[0].cell_id == cell.cell_id

    res = await repo.increment_activations([cell.cell_id])
    assert res == {cell.cell_id: 2}

    fetched = await repo.get(cell.cell_id)
    assert fetched.activation_count == 2

    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    await repo.update_last_scraped([cell.cell_id], now)
    fetched = await repo.get(cell.cell_id)
    assert fetched.last_scraped_at == now

    res = await repo.decrement_activations([cell.cell_id])
    assert res == {cell.cell_id: 1}

    res = await repo.decrement_activations([cell.cell_id])
    assert res == {cell.cell_id: 0}

    fetched = await repo.get(cell.cell_id)
    assert fetched is None

    all_cells: list[MarketCell] = await repo.scan()
    assert len(all_cells) == 0


# --- Offers Repository Integration Tests ---


@pytest.fixture
def test_offer():
    return Offer(
        provider=ProviderName.TUI,
        external_offer_id="TUI-OFFER-INT-1",
        hotel_name="Integration Test Hotel",
        location="Egipt/Hurghada/Hurghada City",
        departure_airport="WAW",
        departure_date=date(2026, 7, 12),
        return_date=date(2026, 7, 19),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=Decimal("4.5"),
        review_count=100,
        price_total=Decimal("5000.00"),
        price_per_person=Decimal("2500.00"),
        price_per_day=Decimal("2500.00"),
        referral_url="https://www.tui.pl/details-eg-1",
        available=True,
        room_type="Family Room Standard",
        adults=2,
        children=0,
        metadata=OfferMetadata(
            tui=TuiMetadata(offer_code="TUI-OFFER-INT-1"),
        ),
        cell_id="1234567890abcdef",
        offer_id="abcdefabcdefabcdefabcdefabcdef12",
        attractiveness_score=0.8,
        share_url="https://wakacje-travelis.pl/offer/123",
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1783814400,
    )


@pytest.mark.asyncio
async def test_offers_repo_integration_lifecycle(offers_table, test_offer):
    repo = DynamoOffersRepository(offers_table)

    await repo.put(test_offer)
    fetched = await repo.get(test_offer.cell_id, test_offer.offer_id)
    assert fetched is not None
    assert fetched.offer_id == test_offer.offer_id
    assert fetched.cell_id == test_offer.cell_id
    assert fetched.hotel_name == "Integration Test Hotel"
    assert fetched.price_total == Decimal("5000.00")

    cell_offers: list[Offer] = await repo.query_by_cell(test_offer.cell_id)
    assert len(cell_offers) == 1
    assert cell_offers[0].offer_id == test_offer.offer_id

    await repo.delete(test_offer.cell_id, test_offer.offer_id)
    assert await repo.get(test_offer.cell_id, test_offer.offer_id) is None


@pytest.mark.asyncio
async def test_offers_repo_integration_batch(offers_table, test_offer):
    repo = DynamoOffersRepository(offers_table)

    offer2 = test_offer.model_copy(
        update={"offer_id": "99999999999999999999999999999999"}
    )

    await repo.put_batch([test_offer, offer2])

    fetched1 = await repo.get(test_offer.cell_id, test_offer.offer_id)
    fetched2 = await repo.get(offer2.cell_id, offer2.offer_id)
    assert fetched1 is not None
    assert fetched2 is not None

    cell_offers: list[Offer] = await repo.query_by_cell(test_offer.cell_id)
    assert len(cell_offers) == 2

    await repo.delete_batch(
        [
            (test_offer.cell_id, test_offer.offer_id),
            (offer2.cell_id, offer2.offer_id),
        ]
    )

    assert await repo.get(test_offer.cell_id, test_offer.offer_id) is None
    assert await repo.get(offer2.cell_id, offer2.offer_id) is None


# --- Users Repository Integration Tests ---


@pytest.fixture
def test_user():
    return User(
        user_id="usr_int_123",
        preferences=UserPreferences(
            countries=["GR", "IT"],
            adults=2,
            min_stars=3,
        ),
        push_enabled=False,
        push_subscription=None,
        created_at=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_users_repo_integration_lifecycle(users_table, test_user):
    repo = DynamoUsersRepository(users_table)

    await repo.put(test_user)
    fetched = await repo.get(test_user.user_id)
    assert fetched is not None
    assert fetched.user_id == test_user.user_id
    assert fetched.preferences.countries == ["GR", "IT"]

    sub = PushSubscription(
        endpoint="https://push.example.com/sub/123",
        keys=PushSubscriptionKeys(p256dh="key_p256dh", auth="key_auth"),
    )
    await repo.update_push(test_user.user_id, enabled=True, subscription=sub)

    fetched = await repo.get(test_user.user_id)
    assert fetched.push_enabled is True
    assert fetched.push_subscription is not None
    assert fetched.push_subscription.endpoint == "https://push.example.com/sub/123"

    await repo.delete(test_user.user_id)
    assert await repo.get(test_user.user_id) is None


# --- UserOffers Repository Integration Tests ---


@pytest.mark.asyncio
async def test_user_offers_repo_integration_lifecycle(user_offers_table):
    repo = DynamoUserOffersRepository(user_offers_table)

    user_id = "usr_int_123"
    offer_id = "off_int_456"
    cell_id = "cell_int_789"
    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)

    await repo.put(user_id, offer_id, cell_id, now)
    fetched = await repo.get(user_id, offer_id)
    assert fetched is not None
    assert fetched["user_id"] == user_id
    assert fetched["offer_id"] == offer_id
    assert fetched["cell_id"] == cell_id

    records = await repo.query_by_user(user_id)
    assert len(records) == 1
    assert records[0]["offer_id"] == offer_id

    await repo.delete(user_id, offer_id)
    assert await repo.get(user_id, offer_id) is None


@pytest.mark.asyncio
async def test_user_offers_repo_integration_batch(user_offers_table):
    repo = DynamoUserOffersRepository(user_offers_table)

    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    items = [
        {
            "user_id": "usr_int_1",
            "offer_id": "off_int_1",
            "cell_id": "cell_int_1",
            "matched_at": now,
        },
        {
            "user_id": "usr_int_1",
            "offer_id": "off_int_2",
            "cell_id": "cell_int_1",
            "matched_at": now,
        },
    ]

    await repo.put_batch(items)

    records = await repo.query_by_user("usr_int_1")
    assert len(records) == 2

    await repo.delete_batch([("usr_int_1", "off_int_1"), ("usr_int_1", "off_int_2")])
    records = await repo.query_by_user("usr_int_1")
    assert len(records) == 0


# --- Redis Feed Repository Integration Tests ---

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


async def test_feed_repo_integration_version(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_int_123"
    assert await repo.get_feed_version(user_id) == 0

    new_ver = await repo.increment_feed_version(user_id)
    assert new_ver == 1
    assert await repo.get_feed_version(user_id) == 1


async def test_feed_repo_integration_zset(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_int_123"
    field = "price"

    assert await repo.get_or_build_sort_zset(user_id, field, "desc", 1) is False

    members = [
        ("offer_int_1:cell_int_1", 1000.5),
        ("offer_int_2:cell_int_1", 500.2),
        ("offer_int_3:cell_int_1", 1500.7),
    ]
    await repo.add_to_sort_zset(user_id, field, "desc", 1, members)

    assert await repo.get_or_build_sort_zset(user_id, field, "desc", 1) is True

    page_desc = await repo.get_page(user_id, field, "desc", 1, offset=0, limit=10)
    assert page_desc == [
        ("offer_int_3", "cell_int_1"),
        ("offer_int_1", "cell_int_1"),
        ("offer_int_2", "cell_int_1"),
    ]


async def test_feed_repo_integration_clear_user(redis_client):
    repo = RedisFeedRepository(redis_client)

    user_id = "usr_int_123"
    await repo.increment_feed_version(user_id)
    await repo.add_to_sort_zset(user_id, "price", "desc", 1, [("offer_int_1", 100.0)])

    assert await redis_client.exists(f"user:{user_id}:feed_version")

    await repo.clear_user(user_id)

    assert not await redis_client.exists(f"user:{user_id}:feed_version")
