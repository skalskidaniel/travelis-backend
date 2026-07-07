import asyncio
from datetime import datetime, timezone
from typing import Any
from botocore.exceptions import ClientError

from core.exceptions.repository import ItemNotFoundException
from core.models.user import User, PushSubscription
from core.repositories.base import UsersRepository
from core.repositories.utils import serialize_item, deserialize_item


class DynamoUsersRepository(UsersRepository):
    """DynamoDB implementation of the UsersRepository."""

    def __init__(self, table: Any) -> None:
        self.table = table

    async def get(self, user_id: str) -> User | None:
        response = await self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if not item:
            return None
        return User(**deserialize_item(item))

    async def put(self, user: User) -> None:
        item = serialize_item(user.model_dump())
        await self.table.put_item(Item=item)

    async def delete(self, user_id: str) -> None:
        await self.table.delete_item(Key={"user_id": user_id})

    async def update_push(
        self, user_id: str, enabled: bool, subscription: PushSubscription | None
    ) -> None:
        sub_item = serialize_item(subscription.model_dump()) if subscription else None
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            await self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET push_enabled = :enabled, push_subscription = :sub, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":enabled": enabled,
                    ":sub": sub_item,
                    ":updated_at": now_str,
                },
                ConditionExpression="attribute_exists(user_id)",
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                raise ItemNotFoundException(f"User not found: {user_id}") from exc
            raise

    async def scan(self) -> list[User]:
        items = []
        exclusive_start_key = None
        # noinspection DuplicatedCode
        while True:
            kwargs = {}
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = await self.table.scan(**kwargs)
            items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        return [User(**deserialize_item(item)) for item in items]

    async def record_session_start(
        self, user_id: str, new_since: datetime, last_active_at: datetime
    ) -> None:
        try:
            await self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET new_since = :ns, last_active_at = :la",
                ExpressionAttributeValues={
                    ":ns": new_since.isoformat(),
                    ":la": last_active_at.isoformat(),
                },
                ConditionExpression="attribute_exists(user_id)",
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                raise ItemNotFoundException(f"User not found: {user_id}") from exc
            raise

    async def mark_inactive(self, user_ids: list[str]) -> int:
        if not user_ids:
            return 0

        async def _update(user_id: str) -> bool:
            try:
                await self.table.update_item(
                    Key={"user_id": user_id},
                    UpdateExpression="SET is_active = :v",
                    ExpressionAttributeValues={":v": False},
                    ConditionExpression=(
                        "attribute_exists(user_id) AND is_active = :true"
                    ),
                )
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code == "ConditionalCheckFailedException":
                    return False
                raise

        results = await asyncio.gather(*[_update(uid) for uid in user_ids])
        return sum(1 for r in results if r)

    async def clear_inactive(self, user_ids: list[str]) -> int:
        if not user_ids:
            return 0

        async def _update(user_id: str) -> bool:
            try:
                await self.table.update_item(
                    Key={"user_id": user_id},
                    UpdateExpression="SET is_active = :v",
                    ExpressionAttributeValues={":v": True},
                    ConditionExpression=(
                        "attribute_exists(user_id) AND is_active = :false"
                    ),
                )
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code == "ConditionalCheckFailedException":
                    return False
                raise

        results = await asyncio.gather(*[_update(uid) for uid in user_ids])
        return sum(1 for r in results if r)

    async def list_users_inactive_since(self, cutoff: datetime) -> list[User]:
        cutoff_str = cutoff.isoformat()
        items: list[User] = []
        exclusive_start_key = None
        while True:
            kwargs: dict = {
                "FilterExpression": ("last_active_at < :cutoff AND is_active = :true"),
                "ExpressionAttributeValues": {
                    ":cutoff": cutoff_str,
                    ":true": True,
                },
            }
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = await self.table.scan(**kwargs)
            items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        return [User(**deserialize_item(item)) for item in items]
