import asyncio
from typing import Any
from boto3.dynamodb.conditions import Key

from core.models.offer import Offer
from core.repositories.base import OffersRepository
from core.repositories.utils import (
    serialize_item,
    deserialize_item,
    chunked,
    BATCH_WRITE_LIMIT,
    BATCH_READ_LIMIT,
)
from core.exceptions.repository import WriteException, ReadException


class DynamoOffersRepository(OffersRepository):
    """DynamoDB implementation of the OffersRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    async def get(self, cell_id: str, offer_id: str) -> Offer | None:
        response = await self.table.get_item(
            Key={"cell_id": cell_id, "offer_id": offer_id}
        )
        item = response.get("Item")
        if not item:
            return None
        return Offer(**deserialize_item(item))

    async def get_batch(self, keys: list[tuple[str, str]]) -> list[Offer]:
        if not keys:
            return []

        client = self.table.meta.client
        table_name = self.table.name

        offers: list[Offer] = []
        for chunk in chunked(keys, BATCH_READ_LIMIT):
            request_items = {
                table_name: {
                    "Keys": [
                        {"cell_id": cell_id, "offer_id": offer_id}
                        for cell_id, offer_id in chunk
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
                    offers.append(Offer(**deserialize_item(item)))

                unprocessed = response.get("UnprocessedKeys", {})
                if unprocessed:
                    retries += 1
                    await asyncio.sleep(0.1 * (2**retries))

            if unprocessed:
                raise ReadException(
                    "Failed to read some offers in batch after retries."
                )

        return offers

    async def put(self, offer: Offer) -> None:
        item = serialize_item(offer.model_dump())
        await self.table.put_item(Item=item)

    async def put_batch(self, offers: list[Offer]) -> None:
        if not offers:
            return

        client = self.table.meta.client
        table_name = self.table.name

        for chunk in chunked(offers, BATCH_WRITE_LIMIT):
            request_items = {
                table_name: [
                    {"PutRequest": {"Item": serialize_item(offer.model_dump())}}
                    for offer in chunk
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
                    "Failed to write some offers in batch after retries."
                )

    async def query_by_cell(self, cell_id: str) -> list[Offer]:
        items = []
        exclusive_start_key = None
        while True:
            kwargs = {"KeyConditionExpression": Key("cell_id").eq(cell_id)}
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = await self.table.query(**kwargs)
            items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        return [Offer(**deserialize_item(item)) for item in items]

    async def delete(self, cell_id: str, offer_id: str) -> None:
        await self.table.delete_item(Key={"cell_id": cell_id, "offer_id": offer_id})

    async def delete_batch(self, keys: list[tuple[str, str]]) -> None:
        if not keys:
            return

        client = self.table.meta.client
        table_name = self.table.name

        for chunk in chunked(keys, BATCH_WRITE_LIMIT):
            request_items = {
                table_name: [
                    {
                        "DeleteRequest": {
                            "Key": {"cell_id": cell_id, "offer_id": offer_id}
                        }
                    }
                    for cell_id, offer_id in chunk
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
                    "Failed to delete some offers in batch after retries."
                )
