from typing import Protocol, runtime_checkable
from datetime import date, datetime

from core.models.cell import MarketCell
from core.models.offer import Offer
from core.models.user import User, PushSubscription


@runtime_checkable
class CellsRepository(Protocol):
    async def get(self, cell_id: str) -> MarketCell | None: ...

    async def get_batch(self, cell_ids: list[str]) -> list[MarketCell]: ...

    async def put(self, cell: MarketCell) -> None: ...

    async def scan(self) -> list[MarketCell]: ...

    async def increment_activations(self, cell_ids: list[str]) -> dict[str, int]: ...

    async def activate_cells(self, cells: list[MarketCell]) -> dict[str, int]: ...

    async def decrement_activations(self, cell_ids: list[str]) -> dict[str, int]: ...

    async def delete(self, cell_id: str) -> None: ...

    async def update_last_scraped(self, cell_ids: list[str], ts: datetime) -> None: ...


@runtime_checkable
class OffersRepository(Protocol):
    async def get(self, cell_id: str, offer_id: str) -> Offer | None: ...

    async def get_batch(self, keys: list[tuple[str, str]]) -> list[Offer]: ...

    async def put(self, offer: Offer) -> None: ...

    async def put_batch(self, offers: list[Offer]) -> None: ...

    async def query_by_cell(self, cell_id: str) -> list[Offer]: ...

    async def scan(self) -> list[Offer]: ...

    async def delete(self, cell_id: str, offer_id: str) -> None: ...

    async def delete_batch(self, keys: list[tuple[str, str]]) -> None: ...


@runtime_checkable
class UsersRepository(Protocol):
    async def get(self, user_id: str) -> User | None: ...

    async def put(self, user: User) -> None: ...

    async def delete(self, user_id: str) -> None: ...

    async def update_push(
        self, user_id: str, enabled: bool, subscription: PushSubscription | None
    ) -> None: ...

    async def scan(self) -> list[User]: ...

    async def touch_last_seen(self, user_id: str, seen_date: date) -> None: ...

    async def mark_inactive(self, user_ids: list[str]) -> int: ...

    async def clear_inactive(self, user_ids: list[str]) -> int: ...

    async def list_users_inactive_since(self, cutoff: date) -> list[User]: ...


@runtime_checkable
class UserOffersRepository(Protocol):
    async def get(self, user_id: str, offer_id: str) -> dict | None: ...

    async def get_batch(self, user_id: str, offer_ids: list[str]) -> list[dict]: ...

    async def put(
        self,
        user_id: str,
        offer_id: str,
        cell_id: str,
        matched_at: datetime,
        favorited: bool = False,
    ) -> None: ...

    async def set_favorite(
        self, user_id: str, offer_id: str, favorited: bool
    ) -> None: ...

    async def query_by_user(self, user_id: str) -> list[dict]: ...

    async def delete(self, user_id: str, offer_id: str) -> None: ...

    async def delete_batch(self, keys: list[tuple[str, str]]) -> None: ...

    async def put_batch(self, items: list[dict]) -> None: ...


@runtime_checkable
class FeedRepository(Protocol):
    async def get_feed_version(self, user_id: str) -> int: ...

    async def increment_feed_version(self, user_id: str) -> int: ...

    async def get_or_build_sort_zset(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        filter_mode: str = "all",
    ) -> bool: ...

    async def add_to_sort_zset(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        members: list[tuple[str, float]],
        filter_mode: str = "all",
    ) -> None: ...

    async def get_page(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        offset: int,
        limit: int,
        filter_mode: str = "all",
    ) -> list[tuple[str, str]]: ...

    async def get_size(
        self,
        user_id: str,
        field: str,
        order: str,
        version: int,
        filter_mode: str = "all",
    ) -> int: ...

    async def clear_user(self, user_id: str) -> None: ...
