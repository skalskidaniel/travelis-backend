import base64
import json
from aws_lambda_powertools import Logger
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status, Path

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.rate_limiter import RateLimiter
from app.offers.schemas import (
    OfferDetailResponse,
    OfferFeedItem,
    PaginatedOffersResponse,
)
from core.container import Container
from core.models.offer import Offer

logger = Logger(child=True)

router = APIRouter(tags=["Offers Feed"])


async def _prune_stale_user_offers(
    container: Container,
    user_id: str,
    requested_keys: list[tuple[str, str]],
    hydrated_offers: list[Offer],
) -> bool:
    """Remove UserOffers rows whose offers no longer exist and bump feed version."""
    returned_keys = {(offer.cell_id, offer.offer_id) for offer in hydrated_offers}
    stale_keys = [key for key in requested_keys if key not in returned_keys]
    if not stale_keys:
        return False

    await container.user_offers_repo.delete_batch(
        [(user_id, offer_id) for _, offer_id in stale_keys]
    )
    await container.feed_repo.increment_feed_version(user_id)
    logger.info(
        "Pruned %d stale UserOffers rows for user %s after missing offer hydration",
        len(stale_keys),
        user_id,
    )
    return True


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


@router.get(
    "",
    response_model=PaginatedOffersResponse,
    summary="Retrieve matched offers feed",
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
    responses={
        200: {
            "description": "Successfully retrieved user's personalized matched feed."
        },
        400: {"description": "Invalid pagination cursor provided."},
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def get_offers_feed(
    sort: str = Query(
        default="attractiveness",
        description="The field by which to sort matched offers.",
        enum=[
            "attractiveness",
            "departure_date",
            "price_total",
            "price_per_day",
            "rating",
            "duration",
        ],
    ),
    order: str = Query(
        default="desc",
        description="Sort direction (ascending or descending).",
        enum=["asc", "desc"],
    ),
    limit: int = Query(
        default=20,
        description="Number of offers to retrieve per page.",
        ge=1,
        le=50,
    ),
    cursor: str | None = Query(
        default=None,
        description="Base64 encoded pagination cursor containing offset and feed version.",
    ),
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
            if not isinstance(cursor_data, dict):
                raise ValueError("cursor must decode to an object")
            offset = int(cursor_data.get("offset", 0))
            if offset < 0:
                raise ValueError("cursor offset must be non-negative")
            cursor_feed_version = cursor_data.get("feed_version")
            if cursor_feed_version is not None and not isinstance(
                cursor_feed_version, int
            ):
                raise ValueError("cursor feed_version must be an integer")
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
        user_offers: list[dict] = await container.user_offers_repo.query_by_user(
            user_id
        )
        if not user_offers:
            return PaginatedOffersResponse(
                offers=[], next_cursor=None, feed_version=current_version, total_count=0
            )

        offer_keys = [(item["cell_id"], item["offer_id"]) for item in user_offers]
        offers: list[Offer] = await container.offers_repo.get_batch(offer_keys)
        if await _prune_stale_user_offers(container, user_id, offer_keys, offers):
            current_version = await container.feed_repo.get_feed_version(user_id)

        valid_offers: list[Offer] = offers

        members = [
            (f"{o.offer_id}:{o.cell_id}", calculate_zset_score(o, sort))
            for o in valid_offers
        ]
        await container.feed_repo.add_to_sort_zset(
            user_id, sort, order, current_version, members
        )
        total_count = len(valid_offers)
    else:
        total_count = await container.feed_repo.get_size(
            user_id=user_id,
            field=sort,
            order=order,
            version=current_version,
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
            offers=[],
            next_cursor=None,
            feed_version=current_version,
            total_count=total_count,
        )

    batch_keys = [
        (cell_id, offer_id) for offer_id, cell_id in offer_keys if offer_id and cell_id
    ]
    hydrated_offers: list[Offer] = await container.offers_repo.get_batch(batch_keys)
    if await _prune_stale_user_offers(container, user_id, batch_keys, hydrated_offers):
        current_version = await container.feed_repo.get_feed_version(user_id)
        total_count = await container.feed_repo.get_size(
            user_id=user_id,
            field=sort,
            order=order,
            version=current_version,
        )

    offer_ids = [oid for oid, _ in offer_keys]
    offer_map = {o.offer_id: o for o in hydrated_offers if o is not None}
    sorted_offers: list[Offer] = [
        offer_map[oid] for oid in offer_ids if oid in offer_map
    ]

    next_cursor = None
    if len(offer_keys) == limit:
        next_cursor_data = {
            "offset": offset + limit,
            "feed_version": current_version,
        }
        next_cursor = base64.b64encode(
            json.dumps(next_cursor_data).encode("utf-8")
        ).decode("utf-8")

    page_user_offers = await container.user_offers_repo.get_batch(user_id, offer_ids)
    favorited_map = {
        item["offer_id"]: item.get("favorited", False) for item in page_user_offers
    }

    feed_items = [
        OfferFeedItem.from_domain(o, favorited=favorited_map.get(o.offer_id, False))
        for o in sorted_offers
    ]

    return PaginatedOffersResponse(
        offers=feed_items,
        next_cursor=next_cursor,
        feed_version=current_version,
        total_count=total_count,
    )


@router.get(
    "/favorites",
    response_model=PaginatedOffersResponse,
    summary="Retrieve favorited offers",
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
    responses={
        200: {"description": "Successfully retrieved user's favorited offers."},
        400: {"description": "Invalid pagination cursor provided."},
        401: {"description": "Unauthorized - Invalid or missing credentials."},
    },
)
async def get_favorites_feed(
    limit: int = Query(
        default=20,
        description="Number of offers to retrieve per page.",
        ge=1,
        le=50,
    ),
    cursor: str | None = Query(
        default=None,
        description="Base64 encoded pagination cursor containing offset.",
    ),
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Retrieve a paginated list of favorited travel offers for the authenticated user."""
    offset = 0

    if cursor:
        try:
            cursor_data = json.loads(
                base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            )
            offset = int(cursor_data.get("offset", 0))
            if offset < 0:
                raise ValueError()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pagination cursor",
            )

    user_offers = await container.user_offers_repo.query_by_user(user_id)
    favorites = [item for item in user_offers if item.get("favorited", False)]
    total_count = len(favorites)

    if not favorites:
        return PaginatedOffersResponse(
            offers=[], next_cursor=None, feed_version=None, total_count=0
        )

    # Sort favorites by matched_at descending
    favorites.sort(key=lambda x: x.get("matched_at", ""), reverse=True)

    page_items = favorites[offset : offset + limit]

    if not page_items:
        return PaginatedOffersResponse(
            offers=[], next_cursor=None, feed_version=None, total_count=total_count
        )

    batch_keys = [(item["cell_id"], item["offer_id"]) for item in page_items]
    hydrated_offers = await container.offers_repo.get_batch(batch_keys)

    # Clean up stale favorites (hydration misses)
    if await _prune_stale_user_offers(container, user_id, batch_keys, hydrated_offers):
        user_offers = await container.user_offers_repo.query_by_user(user_id)
        favorites = [item for item in user_offers if item.get("favorited", False)]
        favorites.sort(key=lambda x: x.get("matched_at", ""), reverse=True)
        total_count = len(favorites)
        page_items = favorites[offset : offset + limit]
        batch_keys = [(item["cell_id"], item["offer_id"]) for item in page_items]
        hydrated_offers = await container.offers_repo.get_batch(batch_keys)

    offer_map = {o.offer_id: o for o in hydrated_offers if o is not None}
    sorted_offers = [
        offer_map[item["offer_id"]]
        for item in page_items
        if item["offer_id"] in offer_map
    ]

    next_cursor = None
    if offset + limit < total_count:
        next_cursor_data = {"offset": offset + limit}
        next_cursor = base64.b64encode(
            json.dumps(next_cursor_data).encode("utf-8")
        ).decode("utf-8")

    feed_items = [OfferFeedItem.from_domain(o, favorited=True) for o in sorted_offers]

    return PaginatedOffersResponse(
        offers=feed_items,
        next_cursor=next_cursor,
        feed_version=None,
        total_count=total_count,
    )


@router.put(
    "/{offer_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Favorite an offer",
    dependencies=[Depends(RateLimiter(times=50, seconds=60))],
    responses={
        204: {"description": "Offer successfully marked as favorite."},
        400: {"description": "cell_id query parameter missing and offer not in feed."},
        401: {"description": "Unauthorized - Invalid or missing credentials."},
        404: {"description": "Offer not found in backend DB."},
    },
)
async def favorite_offer(
    offer_id: str = Path(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    ),
    cell_id: str | None = Query(
        default=None,
        description="The cell ID of the offer. Required if favoriting a shared offer not in feed.",
    ),
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Mark an offer as a favorite. Creates a UserOffers entry if one does not exist."""
    uo_item = await container.user_offers_repo.get(user_id, offer_id)

    if uo_item:
        await container.user_offers_repo.set_favorite(user_id, offer_id, True)
    else:
        if not cell_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cell_id is required to favorite an offer not currently in your feed.",
            )

        # Verify the offer exists in the main Offers table
        offer = await container.offers_repo.get(cell_id, offer_id)
        if not offer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer details not found in database.",
            )

        await container.user_offers_repo.put(
            user_id=user_id,
            offer_id=offer_id,
            cell_id=cell_id,
            matched_at=datetime.now(timezone.utc),
            favorited=True,
        )


@router.delete(
    "/{offer_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfavorite an offer",
    dependencies=[Depends(RateLimiter(times=50, seconds=60))],
    responses={
        204: {"description": "Offer successfully removed from favorites."},
        401: {"description": "Unauthorized - Invalid or missing credentials."},
        404: {"description": "Offer not found or not currently favorited."},
    },
)
async def unfavorite_offer(
    offer_id: str = Path(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    ),
    user_id: str = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Remove an offer from favorites. Deletes UserOffers row if offer doesn't match preferences."""
    uo_item = await container.user_offers_repo.get(user_id, offer_id)
    if not uo_item or not uo_item.get("favorited", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer is not marked as favorite.",
        )

    user = await container.users_repo.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    cell_id = uo_item["cell_id"]
    offer = await container.offers_repo.get(cell_id, offer_id)

    is_match = False
    if offer:
        matches = container.matching_service._filter_offers_vectorized(
            [offer], user.preferences
        )
        is_match = len(matches) > 0

    if is_match:
        await container.user_offers_repo.set_favorite(user_id, offer_id, False)
    else:
        await container.user_offers_repo.delete(user_id, offer_id)


@router.get(
    "/{offer_id}",
    response_model=OfferDetailResponse,
    summary="Get offer details",
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
    responses={
        200: {"description": "Successfully retrieved offer details."},
        401: {"description": "Unauthorized - Invalid or missing credentials."},
        404: {
            "description": "Offer not found in user's matched feed, or details missing."
        },
    },
)
async def get_offer_detail(
    offer_id: str = Path(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    ),
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
    offer: Offer | None = await container.offers_repo.get(cell_id, offer_id)
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer details not found",
        )

    return OfferDetailResponse.from_domain(
        offer, favorited=uo_item.get("favorited", False)
    )


@router.get(
    "/{cell_id}/{offer_id}",
    response_model=OfferDetailResponse,
    summary="Get shared offer details",
    dependencies=[Depends(RateLimiter(times=60, seconds=60))],
    responses={
        200: {
            "description": "Successfully retrieved shared offer details without authentication."
        },
        404: {
            "description": "Shared offer not found with the provided cell_id and offer_id."
        },
    },
)
async def get_shared_offer_detail(
    cell_id: str = Path(
        description="The 16-character hexadecimal SHA-256 hash identifying the market cell.",
        examples=["1f2e3d4c5b6a7f8e"],
    ),
    offer_id: str = Path(
        description="The 32-character hexadecimal SHA-256 fingerprint identifying the offer.",
        examples=["4a8b9c1d2e3f4051627384950a1b2c3d"],
    ),
    container: Container = Depends(get_container),
):
    """Retrieve shared public offer details directly by cell ID and offer ID (requires no auth)."""
    offer: Offer | None = await container.offers_repo.get(cell_id, offer_id)
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared offer not found",
        )

    return OfferDetailResponse.from_domain(offer)
