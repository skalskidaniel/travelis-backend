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
