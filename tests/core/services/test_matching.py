from datetime import date, datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, WakacjePlMetadata
from core.models.user import (
    User,
    UserPreferences,
    PushSubscription,
    PushSubscriptionKeys,
)
from core.services.activation import generate_required_cells
from core.services.matching import MatchingService


@pytest.fixture
def test_user():
    return User(
        user_id="usr_123",
        preferences=UserPreferences(
            countries=["GR"],
            adults=2,
            min_stars=4,
            min_rating=4,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            duration_min=5,
            duration_max=10,
        ),
        push_enabled=True,
        push_subscription=PushSubscription(
            endpoint="https://push.com/usr123",
            keys=PushSubscriptionKeys(p256dh="p256dh", auth="auth"),
        ),
        created_at=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_offers():
    meta_wak = WakacjePlMetadata(
        hotel_id=123,
        tour_operator_id=456,
        tour_op_code="TUIY",
        country_id=1,
        region_id=2,
        city_id=3,
        departure_city_id=4,
        service_id=1,
        transport_id=1,
        departure_slug="z-warszawy",
        offer_page_path="/oferta-123.html",
        adults=2,
        children=0,
    )

    o1 = Offer(
        cell_id="0123456789abcdef",
        offer_id="0123456789abcdef0123456789abcdef",
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="wak_123",
        hotel_name="Greece Resort",
        location="GR/Crete/Chania",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=4.5,
        review_count=100,
        price_total=3000.0,
        price_per_day_one_person=428.5,
        attractiveness_score=0.8,
        referral_url="https://wakacje.pl/ref1",
        image_url="https://image.com/1",
        available=True,
        room_type="Double Room",
        adults=2,
        children=0,
        metadata=OfferMetadata(price_z_score=-1.5, wakacje_pl=meta_wak),
        share_url="https://wakacje-travelis.pl/offer/0123456789abcdef/0123456789abcdef0123456789abcdef",
        scraped_at=datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc),
        ttl=1783641600,
    )
    o2 = Offer(
        cell_id="0123456789abcdef",
        offer_id="fedcba9876543210fedcba9876543210",
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="wak_456",
        hotel_name="Greece Budget",
        location="GR/Crete/Chania",
        departure_airport="WAW",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=2.5,  # Too low (prefs min_rating = 4)
        review_count=100,
        price_total=1500.0,
        price_per_day_one_person=214.2,
        attractiveness_score=0.5,
        referral_url="https://wakacje.pl/ref2",
        image_url="https://image.com/2",
        available=True,
        room_type="Double Room",
        adults=2,
        children=0,
        metadata=OfferMetadata(price_z_score=-1.0, wakacje_pl=meta_wak),
        share_url="https://wakacje-travelis.pl/offer/0123456789abcdef/fedcba9876543210fedcba9876543210",
        scraped_at=datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc),
        ttl=1783641600,
    )
    return [o1, o2]


@pytest.mark.asyncio
async def test_match_user_offers_success(test_user, mock_offers):
    users_repo = MagicMock()
    users_repo.get = AsyncMock(return_value=test_user)

    offers_repo = MagicMock()
    offers_repo.query_by_cell = AsyncMock(return_value=mock_offers)

    user_offers_repo = MagicMock()
    user_offers_repo.query_by_user = AsyncMock(return_value=[])
    user_offers_repo.delete_batch = AsyncMock()
    user_offers_repo.put_batch = AsyncMock()

    feed_repo = MagicMock()
    feed_repo.increment_feed_version = AsyncMock()

    notifications_service = MagicMock()
    notifications_service.send_random_notification = AsyncMock()

    activation_service = MagicMock()

    service = MatchingService(
        users_repo=users_repo,
        offers_repo=offers_repo,
        user_offers_repo=user_offers_repo,
        feed_repo=feed_repo,
        notifications_service=notifications_service,
        activation_service=activation_service,
    )

    ref_date = date(2026, 6, 18)
    feed_changed = await service.match_user_offers("usr_123", ref_date)

    assert feed_changed is True

    offers_repo.query_by_cell.assert_called_once()

    user_offers_repo.put_batch.assert_called_once()
    inserted_items = user_offers_repo.put_batch.call_args[0][0]
    assert len(inserted_items) == 1
    assert inserted_items[0]["offer_id"] == "0123456789abcdef0123456789abcdef"

    feed_repo.increment_feed_version.assert_called_once_with("usr_123")
    notifications_service.send_random_notification.assert_called_once_with(
        test_user.push_subscription
    )


@pytest.mark.asyncio
async def test_match_user_offers_self_healing_month_shift(test_user, mock_offers):
    test_user.preferences.date_from = None
    test_user.preferences.date_to = None

    ref_date = date(2026, 7, 15)

    users_repo = MagicMock()
    users_repo.get = AsyncMock(return_value=test_user)
    users_repo.put = AsyncMock()

    offers_repo = MagicMock()
    offers_repo.query_by_cell = AsyncMock(return_value=[])

    user_offers_repo = MagicMock()
    user_offers_repo.query_by_user = AsyncMock(return_value=[])
    user_offers_repo.delete_batch = AsyncMock()
    user_offers_repo.put_batch = AsyncMock()

    feed_repo = MagicMock()
    activation_service = MagicMock()
    activation_service.update_cell_activations = AsyncMock()

    notifications_service = MagicMock()

    service = MatchingService(
        users_repo=users_repo,
        offers_repo=offers_repo,
        user_offers_repo=user_offers_repo,
        feed_repo=feed_repo,
        notifications_service=notifications_service,
        activation_service=activation_service,
    )

    await service.match_user_offers("usr_123", ref_date)

    activation_service.update_cell_activations.assert_called_once()
    called_args = activation_service.update_cell_activations.call_args[1]
    assert called_args["new_reference_date"] == ref_date
    assert called_args["old_reference_date"] == date(2026, 6, 17)

    users_repo.put.assert_called_once_with(test_user)
    assert test_user.updated_at.month == 7


@pytest.mark.asyncio
async def test_bulk_match_users(test_user):
    users_repo = MagicMock()
    users_repo.scan = AsyncMock(return_value=[test_user])

    service = MatchingService(
        users_repo=users_repo,
        offers_repo=MagicMock(),
        user_offers_repo=MagicMock(),
        feed_repo=MagicMock(),
        notifications_service=MagicMock(),
        activation_service=MagicMock(),
    )

    with patch.object(
        service, "match_user_offers", AsyncMock(return_value=True)
    ) as mock_match:
        matching_cell_id = generate_required_cells(
            test_user.preferences, date(2026, 6, 15)
        )[0].cell_id
        matched = await service.bulk_match_users([matching_cell_id], date(2026, 6, 15))
        assert matched == ["usr_123"]
        mock_match.assert_called_once_with("usr_123", date(2026, 6, 15))

    with patch.object(
        service, "match_user_offers", AsyncMock(return_value=True)
    ) as mock_match:
        matched = await service.bulk_match_users(
            ["some_unrelated_cell"], date(2026, 6, 15)
        )
        assert matched == []
        mock_match.assert_not_called()
