import asyncio
import base64
import json
import logging
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.offers.schemas import (
    OfferDetailResponse,
    OfferFeedItem,
    PaginatedOffersResponse,
)
from core.container import Container
from core.models.offer import Offer

logger = logging.getLogger(__name__)

router = APIRouter()


def calculate_zset_score(offer: Offer, field: str) -> float:
    """Deterministic score builder embedding a lexicographical tie-breaker float fraction."""
    hash_fraction = int(offer.offer_id[:6], 16) / 1e10

    if field == "price_total":
        return float(offer.price_total) + hash_fraction
    elif field == "price_per_day":
        return float(offer.price_per_day) + hash_fraction
    elif field == "attractiveness":
        return (float(offer.attractiveness_score) * 1e8) + hash_fraction
    elif field == "rating":
        return (float(offer.rating) * 1e8) + hash_fraction
    elif field == "departure_date":
        epoch = int(
            datetime.combine(
                offer.departure_date, time.min, tzinfo=timezone.utc
            ).timestamp()
        )
        return float(epoch) + hash_fraction
    elif field == "duration":
        return float(offer.duration) + hash_fraction
    else:
        return hash_fraction


@router.get("", response_model=PaginatedOffersResponse)
async def get_offers_feed(
    sort: str = Query(
        default="attractiveness",
        enum=[
            "attractiveness",
            "departure_date",
            "price_total",
            "price_per_day",
            "rating",
            "duration",
        ],
    ),
    order: str = Query(default="desc", enum=["asc", "desc"]),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Retrieve a paginated, sorted list of travel offers from the user's matched feed."""
    offset = 0
    cursor_feed_version = None

    if cursor:
        try:
            cursor_data = json.loads(
                base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            )
            offset = int(cursor_data.get("offset", 0))
            cursor_feed_version = cursor_data.get("feed_version")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pagination cursor",
            )

    current_version = await container.feed_repo.get_feed_version(user_id)

    if cursor_feed_version is not None and cursor_feed_version != current_version:
        logger.info(
            f"Feed version mismatch (client: {cursor_feed_version}, server: {current_version}). Resetting pagination."
        )
        offset = 0

    zset_exists = await container.feed_repo.get_or_build_sort_zset(
        user_id=user_id,
        field=sort,
        order=order,
        version=current_version,
    )

    if not zset_exists:
        logger.info(
            f"ZSET not cached for user {user_id}, sort {sort}, order {order}, v{current_version}. Building..."
        )
        user_offers = await container.user_offers_repo.query_by_user(user_id)
        if not user_offers:
            return PaginatedOffersResponse(
                offers=[], next_cursor=None, feed_version=current_version
            )

        tasks = [
            container.offers_repo.get(item["cell_id"], item["offer_id"])
            for item in user_offers
        ]
        offers = await asyncio.gather(*tasks)
        valid_offers = [o for o in offers if o is not None]

        members = [
            (f"{o.offer_id}:{o.cell_id}", calculate_zset_score(o, sort))
            for o in valid_offers
        ]
        await container.feed_repo.add_to_sort_zset(
            user_id, sort, order, current_version, members
        )

    offer_keys = await container.feed_repo.get_page(
        user_id=user_id,
        field=sort,
        order=order,
        version=current_version,
        offset=offset,
        limit=limit,
    )

    if not offer_keys:
        return PaginatedOffersResponse(
            offers=[], next_cursor=None, feed_version=current_version
        )

    offer_tasks = [
        container.offers_repo.get(cell_id, offer_id)
        for offer_id, cell_id in offer_keys
        if offer_id and cell_id
    ]
    hydrated_offers = await asyncio.gather(*offer_tasks)

    offer_ids = [oid for oid, _ in offer_keys]
    offer_map = {o.offer_id: o for o in hydrated_offers if o is not None}
    sorted_offers = [offer_map[oid] for oid in offer_ids if oid in offer_map]

    next_cursor = None
    if len(offer_keys) == limit:
        next_cursor_data = {
            "offset": offset + limit,
            "feed_version": current_version,
        }
        next_cursor = base64.b64encode(
            json.dumps(next_cursor_data).encode("utf-8")
        ).decode("utf-8")

    feed_items = [OfferFeedItem.from_domain(o) for o in sorted_offers]

    return PaginatedOffersResponse(
        offers=feed_items, next_cursor=next_cursor, feed_version=current_version
    )


@router.get("/{offer_id}", response_model=OfferDetailResponse)
async def get_offer_detail(
    offer_id: str,
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Retrieve full offer details for an offer present in the user's matched feed."""
    uo_item = await container.user_offers_repo.get(user_id, offer_id)
    if not uo_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found in user feed",
        )

    cell_id = uo_item["cell_id"]
    offer = await container.offers_repo.get(cell_id, offer_id)
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer details not found",
        )

    return OfferDetailResponse.from_domain(offer)


@router.get("/{cell_id}/{offer_id}", response_model=OfferDetailResponse)
async def get_shared_offer_detail(
    cell_id: str,
    offer_id: str,
    container: Container = Depends(get_container),
):
    """Retrieve shared public offer details directly by cell ID and offer ID (requires no auth)."""
    offer = await container.offers_repo.get(cell_id, offer_id)
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared offer not found",
        )

    return OfferDetailResponse.from_domain(offer)
