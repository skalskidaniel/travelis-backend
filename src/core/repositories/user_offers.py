import asyncio
from datetime import datetime
from typing import Any
from boto3.dynamodb.conditions import Key

from core.repositories.base import UserOffersRepository
from core.repositories.utils import (
    serialize_item,
    deserialize_item,
    chunked,
    BATCH_WRITE_LIMIT,
    BATCH_READ_LIMIT,
)
from core.exceptions.repository import WriteException, ReadException


class DynamoUserOffersRepository(UserOffersRepository):
    """DynamoDB implementation of the UserOffersRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    async def get(self, user_id: str, offer_id: str) -> dict | None:
        response = await self.table.get_item(
            Key={"user_id": user_id, "offer_id": offer_id}
        )
        item = response.get("Item")
        if not item:
            return None
        return deserialize_item(item)

    async def get_batch(self, user_id: str, offer_ids: list[str]) -> list[dict]:
        if not offer_ids:
            return []

        client = self.table.meta.client
        table_name = self.table.name

        items: list[dict] = []
        for chunk in chunked(offer_ids, BATCH_READ_LIMIT):
            request_items = {
                table_name: {
                    "Keys": [
                        {"user_id": user_id, "offer_id": offer_id} for offer_id in chunk
                    ],
                    "ConsistentRead": False,
                }
            }

            unprocessed = request_items
            retries = 0
            while unprocessed and retries < 5:
                response = await client.batch_get_item(RequestItems=unprocessed)

                responses = response.get("Responses", {}).get(table_name, [])
                for item in responses:
                    items.append(deserialize_item(item))

                unprocessed = response.get("UnprocessedKeys", {})
                if unprocessed:
                    retries += 1
                    await asyncio.sleep(0.1 * (2**retries))

            if unprocessed:
                raise ReadException(
                    "Failed to read some user offers in batch after retries."
                )

        return items

    async def put(
        self,
        user_id: str,
        offer_id: str,
        cell_id: str,
        matched_at: datetime,
        favorited: bool = False,
    ) -> None:
        item = {
            "user_id": user_id,
            "offer_id": offer_id,
            "cell_id": cell_id,
            "matched_at": matched_at,
            "favorited": favorited,
        }
        await self.table.put_item(Item=serialize_item(item))

    async def set_favorite(self, user_id: str, offer_id: str, favorited: bool) -> None:
        await self.table.update_item(
            Key={"user_id": user_id, "offer_id": offer_id},
            UpdateExpression="SET favorited = :f",
            ExpressionAttributeValues={":f": favorited},
        )

    async def query_by_user(self, user_id: str) -> list[dict]:
        items = []
        exclusive_start_key = None
        while True:
            kwargs = {"KeyConditionExpression": Key("user_id").eq(user_id)}
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = await self.table.query(**kwargs)
            items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        return [deserialize_item(item) for item in items]

    async def delete(self, user_id: str, offer_id: str) -> None:
        await self.table.delete_item(Key={"user_id": user_id, "offer_id": offer_id})

    async def delete_batch(self, keys: list[tuple[str, str]]) -> None:
        if not keys:
            return

        client = self.table.meta.client
        table_name = self.table.name

        # noinspection DuplicatedCode
        for chunk in chunked(keys, BATCH_WRITE_LIMIT):
            request_items = {
                table_name: [
                    {
                        "DeleteRequest": {
                            "Key": {"user_id": user_id, "offer_id": offer_id}
                        }
                    }
                    for user_id, offer_id in chunk
                ]
            }

            unprocessed = request_items
            retries = 0
            while unprocessed and retries < 5:
                response = await client.batch_write_item(RequestItems=unprocessed)
                unprocessed = response.get("UnprocessedItems", {})
                if unprocessed:
                    retries += 1
                    await asyncio.sleep(0.1 * (2**retries))

            if unprocessed:
                raise WriteException(
                    "Failed to delete some user offers in batch after retries."
                )

    async def put_batch(self, items: list[dict]) -> None:
        if not items:
            return

        client = self.table.meta.client
        table_name = self.table.name

        # noinspection DuplicatedCode
        for chunk in chunked(items, BATCH_WRITE_LIMIT):
            request_items = {
                table_name: [
                    {"PutRequest": {"Item": serialize_item(item)}} for item in chunk
                ]
            }

            unprocessed = request_items
            retries = 0
            while unprocessed and retries < 5:
                response = await client.batch_write_item(RequestItems=unprocessed)
                unprocessed = response.get("UnprocessedItems", {})
                if unprocessed:
                    retries += 1
                    await asyncio.sleep(0.1 * (2**retries))

            if unprocessed:
                raise WriteException(
                    "Failed to write some user offers in batch after retries."
                )
