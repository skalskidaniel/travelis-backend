import inspect
from botocore.awsrequest import AWSResponse
import pytest
import pytest_asyncio
from moto import mock_aws
import aioboto3
import fakeredis


# Monkeypatch AWSResponse.content to work with aiobotocore's async expectations
class AwaitableBytes:
    def __init__(self, value: bytes):
        self.value = value

    def __await__(self):
        async def _inner():
            return self.value

        return _inner().__await__()


_original_content_property = AWSResponse.content


def patched_content_getter(self):
    val = _original_content_property.fget(self)
    if inspect.isawaitable(val) or hasattr(val, "__await__"):
        return val
    if val is None:
        return AwaitableBytes(b"")
    return AwaitableBytes(val)


fset = getattr(AWSResponse.content, "fset", None)
fdel = getattr(AWSResponse.content, "fdel", None)
setattr(AWSResponse, "content", property(patched_content_getter, fset, fdel))


@pytest.fixture(scope="function")
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture(scope="function")
def mock_aws_env(aws_credentials):
    with mock_aws():
        yield


@pytest_asyncio.fixture(scope="function")
async def dynamodb_resource(mock_aws_env):
    session = aioboto3.Session()
    async with session.resource("dynamodb", region_name="us-east-1") as resource:
        yield resource


@pytest_asyncio.fixture(scope="function")
async def cells_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="MarketCells",
        KeySchema=[{"AttributeName": "cell_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "cell_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


@pytest_asyncio.fixture(scope="function")
async def offers_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="Offers",
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
    return table


@pytest_asyncio.fixture(scope="function")
async def users_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="Users",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


@pytest_asyncio.fixture(scope="function")
async def user_offers_table(dynamodb_resource):
    table = await dynamodb_resource.create_table(
        TableName="UserOffers",
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
    return table


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()
