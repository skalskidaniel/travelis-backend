import asyncio
from datetime import datetime
from typing import Any
from botocore.exceptions import ClientError

from core.exceptions.repository import ItemNotFoundException
from core.models.cell import MarketCell
from core.repositories.base import CellsRepository
from core.repositories.utils import serialize_item, deserialize_item


class DynamoCellsRepository(CellsRepository):
    """DynamoDB implementation of the CellsRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    async def get(self, cell_id: str) -> MarketCell | None:
        response = await self.table.get_item(Key={"cell_id": cell_id})
        item = response.get("Item")
        if not item:
            return None
        return MarketCell(**deserialize_item(item))

    async def put(self, cell: MarketCell) -> None:
        item = serialize_item(cell.model_dump())
        await self.table.put_item(Item=item)

    async def scan(self) -> list[MarketCell]:
        items = []
        exclusive_start_key = None
        while True:
            kwargs = {}
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = await self.table.scan(**kwargs)
            items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        return [MarketCell(**deserialize_item(item)) for item in items]

    async def increment_activations(self, cell_ids: list[str]) -> dict[str, int]:
        if not cell_ids:
            return {}

        async def _update(cell_id: str) -> tuple[str, int]:
            try:
                response = await self.table.update_item(
                    Key={"cell_id": cell_id},
                    UpdateExpression="ADD activation_count :one",
                    ExpressionAttributeValues={":one": 1},
                    ConditionExpression="attribute_exists(cell_id)",
                    ReturnValues="UPDATED_NEW",
                )
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code == "ConditionalCheckFailedException":
                    raise ItemNotFoundException(f"Cell not found: {cell_id}") from exc
                raise
            new_count = int(response["Attributes"]["activation_count"])
            return cell_id, new_count

        results = await asyncio.gather(*[_update(cid) for cid in cell_ids])
        return dict(results)

    async def activate_cells(self, cells: list[MarketCell]) -> dict[str, int]:
        if not cells:
            return {}

        async def _activate(cell: MarketCell) -> tuple[str, int]:
            if cell.cell_id is None:
                msg = "cell_id is required to activate a market cell"
                raise ValueError(msg)

            response = await self.table.update_item(
                Key={"cell_id": cell.cell_id},
                UpdateExpression=(
                    "SET country = if_not_exists(country, :country), "
                    "#month = if_not_exists(#month, :month), "
                    "min_stars = if_not_exists(min_stars, :min_stars), "
                    "board = if_not_exists(board, :board), "
                    "adults = if_not_exists(adults, :adults), "
                    "children = if_not_exists(children, :children) "
                    "ADD activation_count :one"
                ),
                ExpressionAttributeNames={"#month": "month"},
                ExpressionAttributeValues={
                    ":country": cell.country,
                    ":month": cell.month,
                    ":min_stars": cell.min_stars,
                    ":board": cell.board.value,
                    ":adults": cell.adults,
                    ":children": cell.children,
                    ":one": 1,
                },
                ReturnValues="UPDATED_NEW",
            )
            new_count = int(response["Attributes"]["activation_count"])
            return cell.cell_id, new_count

        results = await asyncio.gather(*[_activate(cell) for cell in cells])
        return dict(results)

    async def decrement_activations(self, cell_ids: list[str]) -> dict[str, int]:
        if not cell_ids:
            return {}

        async def _update(cell_id: str) -> tuple[str, int]:
            try:
                response = await self.table.update_item(
                    Key={"cell_id": cell_id},
                    UpdateExpression="ADD activation_count :neg_one",
                    ExpressionAttributeValues={":neg_one": -1},
                    ConditionExpression="attribute_exists(cell_id)",
                    ReturnValues="UPDATED_NEW",
                )
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code == "ConditionalCheckFailedException":
                    raise ItemNotFoundException(f"Cell not found: {cell_id}") from exc
                raise
            new_count = int(response["Attributes"]["activation_count"])
            if new_count <= 0:
                await self.table.delete_item(Key={"cell_id": cell_id})
                return cell_id, 0
            return cell_id, new_count

        results = await asyncio.gather(*[_update(cid) for cid in cell_ids])
        return dict(results)

    async def delete(self, cell_id: str) -> None:
        await self.table.delete_item(Key={"cell_id": cell_id})

    async def update_last_scraped(self, cell_ids: list[str], ts: datetime) -> None:
        if not cell_ids:
            return

        ts_str = ts.isoformat()

        async def _update(cell_id: str) -> None:
            await self.table.update_item(
                Key={"cell_id": cell_id},
                UpdateExpression="SET last_scraped_at = :ts",
                ExpressionAttributeValues={":ts": ts_str},
            )

        await asyncio.gather(*[_update(cid) for cid in cell_ids])


stream = None
