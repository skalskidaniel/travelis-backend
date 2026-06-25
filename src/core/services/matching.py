import asyncio
from aws_lambda_powertools import Logger
from datetime import date, datetime, timezone

from core.models.cell import MarketCell
from core.models.user import User, UserPreferences
from core.models.offer import Offer
from core.repositories.base import (
    UsersRepository,
    OffersRepository,
    UserOffersRepository,
    FeedRepository,
)
from core.services.activation import generate_required_cells, ActivationService
from core.services.notifications import NotificationsService, PushSendResult

logger = Logger(child=True)


class MatchingService:
    """Orchestrates comparing offers against user travel preferences, persisting matches, and sending alerts."""

    def __init__(
        self,
        users_repo: UsersRepository,
        offers_repo: OffersRepository,
        user_offers_repo: UserOffersRepository,
        feed_repo: FeedRepository,
        notifications_service: NotificationsService,
        activation_service: ActivationService,
    ) -> None:
        self.users_repo = users_repo
        self.offers_repo = offers_repo
        self.user_offers_repo = user_offers_repo
        self.feed_repo = feed_repo
        self.notifications_service = notifications_service
        self.activation_service = activation_service

    async def match_user_offers(
        self,
        user_id: str,
        reference_date: date | None = None,
        user: User | None = None,
    ) -> bool:
        """Matches offers for a single user, updates their matches in UserOffers, and invalidates feed."""
        if user is None:
            user: User | None = await self.users_repo.get(user_id)
        if not user:
            logger.warning(f"User not found for matching: {user_id}")
            return False

        ref = reference_date or date.today()
        prefs: UserPreferences = user.preferences

        # 1. Self-Healing Month Shifting
        if prefs.date_from is None and prefs.date_to is None:
            updated_date = user.updated_at.date()
            if ref.year != updated_date.year or ref.month != updated_date.month:
                logger.info(
                    f"Self-healing: shifting active months for user {user_id} from {updated_date} to {ref}"
                )
                current_time = datetime.now(timezone.utc).time()
                user.updated_at = datetime.combine(
                    ref, current_time, tzinfo=timezone.utc
                )
                await self.users_repo.put(user)
                await self.activation_service.update_cell_activations(
                    new_prefs=prefs,
                    old_prefs=prefs,
                    new_reference_date=ref,
                    old_reference_date=updated_date,
                )

        # 2. Resolve required cell IDs
        required_cells: list[MarketCell] = generate_required_cells(prefs, ref)
        logger.debug(
            "Resolved %d required cells for user %s: %s",
            len(required_cells),
            user_id,
            [c.cell_id for c in required_cells],
        )
        if not required_cells:
            existing_items = await self.user_offers_repo.query_by_user(user_id)
            if not existing_items:
                return False

            await self.user_offers_repo.delete_batch(
                [(user_id, item["offer_id"]) for item in existing_items]
            )
            await self.feed_repo.increment_feed_version(user_id)
            return True

        # 3. Query Offers for those cells in parallel
        cell_offers_lists = await asyncio.gather(
            *[self.offers_repo.query_by_cell(cell.cell_id) for cell in required_cells]
        )
        offers: list[Offer] = [
            offer for sublist in cell_offers_lists for offer in sublist
        ]
        logger.debug(
            "Queried %d raw offers from %d cells for user %s",
            len(offers),
            len(required_cells),
            user_id,
        )

        # 4. Filter offers in Python using Pandas/NumPy
        matched_offers: list[Offer] = await asyncio.to_thread(
            self._filter_offers_vectorized, offers, prefs
        )
        logger.debug(
            "Vectorized filtering complete for user %s: %d matches out of %d total offers",
            user_id,
            len(matched_offers),
            len(offers),
        )

        # 5. Sync UserOffers rows
        existing_items = await self.user_offers_repo.query_by_user(user_id)
        existing_offer_ids = {item["offer_id"] for item in existing_items}
        favorited_offer_ids = {
            item["offer_id"] for item in existing_items if item.get("favorited")
        }
        new_offer_ids = {o.offer_id for o in matched_offers}

        to_delete_ids = (existing_offer_ids - new_offer_ids) - favorited_offer_ids
        to_insert_offers: list[Offer] = [
            o for o in matched_offers if o.offer_id not in existing_offer_ids
        ]

        feed_changed = len(to_delete_ids) > 0 or len(to_insert_offers) > 0
        logger.debug(
            "Feed diff for user %s: to_delete=%d, to_insert=%d, feed_changed=%s",
            user_id,
            len(to_delete_ids),
            len(to_insert_offers),
            feed_changed,
        )

        if to_insert_offers:
            matched_at = datetime.now(timezone.utc)
            items_to_insert = [
                {
                    "user_id": user_id,
                    "offer_id": o.offer_id,
                    "cell_id": o.cell_id,
                    "matched_at": matched_at,
                }
                for o in to_insert_offers
            ]
            await self.user_offers_repo.put_batch(items_to_insert)

        if to_delete_ids:
            await self.user_offers_repo.delete_batch(
                [(user_id, oid) for oid in to_delete_ids]
            )

        # 6. If feed changed, increment feed version in Redis and send Web Push
        if feed_changed:
            await self.feed_repo.increment_feed_version(user_id)
            if to_insert_offers and user.push_enabled and user.push_subscription:
                result = await self.notifications_service.send_random_notification(
                    user.push_subscription
                )
                if result is PushSendResult.EXPIRED:
                    await self.users_repo.update_push(
                        user_id, enabled=False, subscription=None
                    )

        return feed_changed

    def _filter_offers_vectorized(
        self, offers: list[Offer], prefs: UserPreferences
    ) -> list[Offer]:
        """Apply vectorized NumPy/Pandas filtering on a list of Offer objects."""
        if not offers:
            return []

        import pandas as pd

        offers_data = [
            {
                "rating": o.rating,
                "departure_airport": o.departure_airport,
                "duration": o.duration,
                "departure_date": o.departure_date,
                "return_date": o.return_date,
                "children": o.children,
                "available": o.available,
            }
            for o in offers
        ]
        df = pd.DataFrame(offers_data)
        logger.debug("Starting vectorized filtering on %d offers", len(df))

        df = df[df["available"]]
        logger.debug("Filtered by availability (available=True): %d remaining", len(df))
        if df.empty:
            return []

        df = df[df["rating"] >= prefs.min_rating]
        logger.debug(
            "Filtered by rating (min=%s): %d remaining", prefs.min_rating, len(df)
        )
        if df.empty:
            return []

        if prefs.departure_airports:
            pref_airports = {a.upper().strip() for a in prefs.departure_airports}
            df = df[df["departure_airport"].str.upper().str.strip().isin(pref_airports)]
            logger.debug(
                "Filtered by departure airports (%s): %d remaining",
                pref_airports,
                len(df),
            )
            if df.empty:
                return []

        df = df[df["duration"] >= prefs.duration_min]
        if prefs.duration_max is not None:
            df = df[df["duration"] <= prefs.duration_max]
        logger.debug(
            "Filtered by duration (min=%s, max=%s): %d remaining",
            prefs.duration_min,
            prefs.duration_max,
            len(df),
        )
        if df.empty:
            return []

        if prefs.date_from is not None:
            df = df[df["departure_date"] >= prefs.date_from]
        if prefs.date_to is not None:
            df = df[df["return_date"] <= prefs.date_to]
        logger.debug(
            "Filtered by travel dates (from=%s, to=%s): %d remaining",
            prefs.date_from,
            prefs.date_to,
            len(df),
        )
        if df.empty:
            return []

        df = df[df["children"] == len(prefs.children)]
        logger.debug(
            "Filtered by children count (expected=%d): %d remaining",
            len(prefs.children),
            len(df),
        )
        if df.empty:
            return []

        if prefs.children:
            departure_dates = pd.to_datetime(df["departure_date"])
            for dob in prefs.children:
                years_diff = departure_dates.dt.year - dob.year
                is_before_birthday = (departure_dates.dt.month < dob.month) | (
                    (departure_dates.dt.month == dob.month)
                    & (departure_dates.dt.day < dob.day)
                )
                ages = years_diff - is_before_birthday.astype(int)
                df = df[(ages >= 0) & (ages < 18)]
                if df.empty:
                    return []

        return [offers[i] for i in df.index]

    async def bulk_match_users(
        self,
        affected_cell_ids: list[str],
        reference_date: date | None = None,
    ) -> list[str]:
        """Scan all users, identify those whose preferences overlap with the affected cells,
        and perform matching for them. Returns the list of matched user IDs.
        """
        if not affected_cell_ids:
            return []

        affected_set = set(affected_cell_ids)
        users = await self.users_repo.scan()
        logger.debug(
            "Scanning %d users for bulk match candidates against %d cells",
            len(users),
            len(affected_cell_ids),
        )

        matched_user_ids = []
        for user in users:
            user_cells: list[MarketCell] = generate_required_cells(
                user.preferences, reference_date
            )
            user_cell_ids = {c.cell_id for c in user_cells}

            if user_cell_ids & affected_set:
                logger.debug(
                    "User %s matches affected cells (overlap: %s); running match_user_offers",
                    user.user_id,
                    user_cell_ids & affected_set,
                )
                feed_changed = await self.match_user_offers(
                    user.user_id, reference_date, user=user
                )
                if feed_changed:
                    matched_user_ids.append(user.user_id)

        return matched_user_ids
