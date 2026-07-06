import base64
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.dependencies import get_container
from app.main import app
from app.offers.controller import calculate_zset_score, resolve_feed_filter_mode
from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, OfferSource, TuiMetadata


@pytest.fixture
def mock_container():
    c = MagicMock()
    c.feed_repo = AsyncMock()
    c.user_offers_repo = AsyncMock()
    c.offers_repo = AsyncMock()
    c.cells_repo = AsyncMock()
    c.settings = MagicMock()
    return c


@pytest.fixture
def client(mock_container):
    app.dependency_overrides[get_container] = lambda: mock_container
    app.dependency_overrides[get_current_user] = lambda: "user-123"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {}


@pytest.fixture
def sample_domain_offer() -> Offer:
    metadata = OfferMetadata(
        price_z_score=0.5,
        sources=[
            OfferSource(
                provider=ProviderName.TUI,
                external_offer_id="ext-123",
                price_total=Decimal("1000.00"),
            )
        ],
        tui=TuiMetadata(offer_code="ext-123"),
    )
    return Offer(
        cell_id="1a2b3c4d5e6f7a8b",
        offer_id="1a2b3c4d5e6f7a8b1a2b3c4d5e6f7a8b",
        attractiveness_score=0.92,
        provider=ProviderName.TUI,
        external_offer_id="ext-123",
        hotel_name="Test Hotel",
        location="Greece/Crete/Ierapetra",
        departure_airport="WAW",
        departure_date=date(2026, 6, 20),
        return_date=date(2026, 6, 27),
        duration=7,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=4.5,
        review_count=100,
        price_total=Decimal("1000.00"),
        price_per_person=Decimal("500.00"),
        price_per_day=Decimal("142.86"),
        referral_url="https://tui.pl/ref",
        image_url="https://tui.pl/img.jpg",
        share_url="https://wakacje-travelis.pl/offer/1a2b3c4d5e6f7a8b/1a2b3c4d5e6f7a8b1a2b3c4d5e6f7a8b",
        available=True,
        room_type="Double Room",
        adults=2,
        children=0,
        metadata=metadata,
        scraped_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ttl=1781913600,
    )


def test_get_offers_empty_feed(client, mock_container, auth_headers):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = False
    mock_container.user_offers_repo.query_by_user.return_value = []

    response = client.get("/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["offers"] == []
    assert data["next_cursor"] is None
    assert data["feed_version"] == 1
    assert data["total_count"] == 0


def test_get_offers_cached_feed(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 42
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 1

    offer_id = sample_domain_offer.offer_id
    mock_container.feed_repo.get_page.return_value = [
        (offer_id, sample_domain_offer.cell_id)
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    response = client.get("/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == offer_id
    assert data["feed_version"] == 42
    assert data["next_cursor"] is None
    assert data["total_count"] == 1


def test_get_offers_build_zset(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = False

    offer_id = sample_domain_offer.offer_id
    mock_container.user_offers_repo.query_by_user.return_value = [
        {"offer_id": offer_id, "cell_id": sample_domain_offer.cell_id}
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    mock_container.feed_repo.get_page.return_value = [
        (offer_id, sample_domain_offer.cell_id)
    ]

    response = client.get("/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == offer_id
    assert data["total_count"] == 1

    # Assert ZSET was built
    mock_container.feed_repo.add_to_sort_zset.assert_called_once()


def test_get_offers_outdated_cursor_resets(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 50
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 1
    mock_container.feed_repo.get_page.return_value = [
        (sample_domain_offer.offer_id, sample_domain_offer.cell_id)
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    # Cursor with version 49
    cursor_data = {"offset": 20, "feed_version": 49}
    cursor_str = base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode(
        "utf-8"
    )

    response = client.get(f"/v2/offers?cursor={cursor_str}", headers=auth_headers)
    assert response.status_code == 200

    # It should query page 1 (offset=0, limit=20) instead of offset 20 from cursor due to mismatch
    mock_container.feed_repo.get_page.assert_called_once_with(
        user_id="user-123",
        field="attractiveness",
        order="desc",
        version=50,
        offset=0,
        limit=20,
        filter_mode="all",
    )


def test_get_offer_detail_matched(
    client, mock_container, auth_headers, sample_domain_offer
):
    offer_id = sample_domain_offer.offer_id
    mock_container.user_offers_repo.get.return_value = {
        "offer_id": offer_id,
        "cell_id": "cell-1",
    }
    mock_container.offers_repo.get.return_value = sample_domain_offer

    response = client.get(f"/v2/offers/{offer_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["offer_id"] == offer_id
    assert data["hotel_name"] == "Test Hotel"


def test_get_offer_detail_not_matched(client, mock_container, auth_headers):
    mock_container.user_offers_repo.get.return_value = None

    response = client.get("/v2/offers/some-offer-id", headers=auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_shared_offer_detail(client, mock_container, sample_domain_offer):
    offer_id = sample_domain_offer.offer_id
    mock_container.offers_repo.get.return_value = sample_domain_offer

    # Unauthenticated request
    response = client.get(f"/v2/offers/cell-123/{offer_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["offer_id"] == offer_id


def test_get_shared_offer_detail_not_found(client, mock_container):
    mock_container.offers_repo.get.return_value = None

    response = client.get("/v2/offers/cell-123/some-offer-id")
    assert response.status_code == 404


def test_get_offers_invalid_cursor(client, auth_headers):
    response = client.get("/v2/offers?cursor=not-base-64", headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid pagination cursor" in response.json()["detail"]


def test_get_offers_rejects_negative_cursor_offset(
    client, mock_container, auth_headers
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    cursor_data = {"offset": -5, "feed_version": 1}
    cursor_str = base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode(
        "utf-8"
    )

    response = client.get(f"/v2/offers?cursor={cursor_str}", headers=auth_headers)

    assert response.status_code == 400


def test_get_offers_prunes_stale_user_offers_on_hydration_miss(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 1
    mock_container.feed_repo.get_page.return_value = [
        (sample_domain_offer.offer_id, sample_domain_offer.cell_id)
    ]
    mock_container.offers_repo.get_batch.return_value = []
    mock_container.feed_repo.increment_feed_version.return_value = 2
    mock_container.feed_repo.get_feed_version.side_effect = [1, 2]
    mock_container.feed_repo.get_size.return_value = 0

    response = client.get("/v2/offers", headers=auth_headers)

    assert response.status_code == 200
    mock_container.user_offers_repo.delete_batch.assert_called_once_with(
        [("user-123", sample_domain_offer.offer_id)]
    )
    mock_container.feed_repo.increment_feed_version.assert_called_once_with("user-123")


def test_get_offer_detail_missing_from_offers_table(
    client, mock_container, auth_headers
):
    mock_container.user_offers_repo.get.return_value = {
        "offer_id": "offer-1",
        "cell_id": "cell-1",
    }
    mock_container.offers_repo.get.return_value = None

    response = client.get("/v2/offers/offer-1", headers=auth_headers)
    assert response.status_code == 404
    assert "Offer details not found" in response.json()["detail"]


def test_get_offers_empty_page_from_zset(client, mock_container, auth_headers):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 10
    # ZSET exists but returns empty keys (e.g. offset beyond total size)
    mock_container.feed_repo.get_page.return_value = []

    response = client.get("/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["offers"] == []
    assert response.json()["total_count"] == 10


def test_get_offers_with_next_cursor(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 2

    # Return exactly limit (limit=2) offers to trigger next_cursor logic
    offer_id = sample_domain_offer.offer_id
    mock_container.feed_repo.get_page.return_value = [
        (offer_id, sample_domain_offer.cell_id),
        ("offer-2", sample_domain_offer.cell_id),
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    response = client.get("/v2/offers?limit=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["next_cursor"] is not None
    assert data["total_count"] == 2


def test_calculate_zset_score_coverage(sample_domain_offer):
    assert calculate_zset_score(sample_domain_offer, "price_total") > 0
    assert calculate_zset_score(sample_domain_offer, "price_per_day") > 0
    assert calculate_zset_score(sample_domain_offer, "rating") > 0
    assert calculate_zset_score(sample_domain_offer, "departure_date") > 0
    assert calculate_zset_score(sample_domain_offer, "duration") > 0
    assert calculate_zset_score(sample_domain_offer, "unknown_field") > 0


def test_resolve_feed_filter_mode_defaults():
    assert resolve_feed_filter_mode(None, False) == "all"
    assert resolve_feed_filter_mode(None, True) == "new"
    assert resolve_feed_filter_mode("gr", False) == "country:GR"


def test_get_offers_rejects_combined_country_and_new_filters(client, auth_headers):
    response = client.get("/v2/offers?country=GR&new=true", headers=auth_headers)
    assert response.status_code == 400
    assert "Cannot combine country and new filters" in response.json()["detail"]


def test_get_offers_rejects_invalid_country_code(client, auth_headers):
    response = client.get("/v2/offers?country=ZZ", headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid country code" in response.json()["detail"]


def test_get_offers_country_filter_builds_country_scoped_zset(
    client, mock_container, auth_headers, sample_domain_offer
):
    other_offer = sample_domain_offer.model_copy(
        update={
            "offer_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "cell_id": "bbbbbbbbbbbbbbbb",
            "location": "Spain/Mallorca/Palma",
        }
    )
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = False
    mock_container.user_offers_repo.query_by_user.return_value = [
        {
            "offer_id": sample_domain_offer.offer_id,
            "cell_id": sample_domain_offer.cell_id,
            "matched_at": datetime.now(timezone.utc),
        },
        {
            "offer_id": other_offer.offer_id,
            "cell_id": other_offer.cell_id,
            "matched_at": datetime.now(timezone.utc),
        },
    ]
    mock_container.offers_repo.get_batch.return_value = [
        sample_domain_offer,
        other_offer,
    ]
    mock_container.cells_repo.get_batch.return_value = [
        MagicMock(cell_id=sample_domain_offer.cell_id, country="GR"),
        MagicMock(cell_id=other_offer.cell_id, country="ES"),
    ]
    mock_container.feed_repo.get_page.return_value = [
        (sample_domain_offer.offer_id, sample_domain_offer.cell_id)
    ]

    response = client.get("/v2/offers?country=GR", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == sample_domain_offer.offer_id
    assert data["total_count"] == 1
    mock_container.feed_repo.add_to_sort_zset.assert_called_once()
    assert (
        mock_container.feed_repo.add_to_sort_zset.call_args.kwargs["filter_mode"]
        == "country:GR"
    )


def test_get_offers_new_filter_builds_new_scoped_zset(
    client, mock_container, auth_headers, sample_domain_offer
):
    recent_matched_at = datetime.now(timezone.utc)
    stale_matched_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stale_offer = sample_domain_offer.model_copy(
        update={
            "offer_id": "cccccccccccccccccccccccccccccccc",
            "cell_id": "cccccccccccccccc",
        }
    )
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = False
    mock_container.user_offers_repo.query_by_user.return_value = [
        {
            "offer_id": sample_domain_offer.offer_id,
            "cell_id": sample_domain_offer.cell_id,
            "matched_at": recent_matched_at,
        },
        {
            "offer_id": stale_offer.offer_id,
            "cell_id": stale_offer.cell_id,
            "matched_at": stale_matched_at,
        },
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer, stale_offer]
    mock_container.feed_repo.get_page.return_value = [
        (sample_domain_offer.offer_id, sample_domain_offer.cell_id)
    ]

    response = client.get("/v2/offers?new=true", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == sample_domain_offer.offer_id
    assert data["total_count"] == 1
    mock_container.feed_repo.add_to_sort_zset.assert_called_once()
    assert mock_container.feed_repo.add_to_sort_zset.call_args.kwargs["filter_mode"] == "new"


def test_get_offers_country_filter_pagination_uses_filter_mode(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_size.return_value = 1
    mock_container.feed_repo.get_page.return_value = [
        (sample_domain_offer.offer_id, sample_domain_offer.cell_id)
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    response = client.get("/v2/offers?country=GR", headers=auth_headers)

    assert response.status_code == 200
    mock_container.feed_repo.get_or_build_sort_zset.assert_called_once_with(
        user_id="user-123",
        field="attractiveness",
        order="desc",
        version=1,
        filter_mode="country:GR",
    )
    mock_container.feed_repo.get_page.assert_called_once_with(
        user_id="user-123",
        field="attractiveness",
        order="desc",
        version=1,
        offset=0,
        limit=20,
        filter_mode="country:GR",
    )


def test_favorite_offer_existing(client, mock_container, auth_headers):
    # Offer is already in UserOffers table
    mock_container.user_offers_repo.get.return_value = {
        "user_id": "user-123",
        "offer_id": "offer-123",
        "cell_id": "cell-123",
        "favorited": False,
    }

    response = client.put("/v2/offers/offer-123/favorite", headers=auth_headers)
    assert response.status_code == 204
    mock_container.user_offers_repo.set_favorite.assert_called_once_with(
        "user-123", "offer-123", True
    )


def test_favorite_offer_new_shared_success(
    client, mock_container, auth_headers, sample_domain_offer
):
    # Offer not in UserOffers table, cell_id provided, exists in Offers table
    mock_container.user_offers_repo.get.return_value = None
    mock_container.offers_repo.get.return_value = sample_domain_offer

    response = client.put(
        "/v2/offers/offer-123/favorite?cell_id=cell-123",
        headers=auth_headers,
    )
    assert response.status_code == 204
    mock_container.offers_repo.get.assert_called_once_with("cell-123", "offer-123")
    mock_container.user_offers_repo.put.assert_called_once()
    # verify user_id, offer_id, cell_id, favorited=True are passed
    kwargs = mock_container.user_offers_repo.put.call_args.kwargs
    assert kwargs["user_id"] == "user-123"
    assert kwargs["offer_id"] == "offer-123"
    assert kwargs["cell_id"] == "cell-123"
    assert kwargs["favorited"] is True


def test_favorite_offer_new_shared_missing_cell_id(
    client, mock_container, auth_headers
):
    mock_container.user_offers_repo.get.return_value = None

    response = client.put("/v2/offers/offer-123/favorite", headers=auth_headers)
    assert response.status_code == 400
    assert "cell_id is required" in response.json()["detail"]


def test_favorite_offer_new_shared_not_found(client, mock_container, auth_headers):
    mock_container.user_offers_repo.get.return_value = None
    mock_container.offers_repo.get.return_value = None

    response = client.put(
        "/v2/offers/offer-123/favorite?cell_id=cell-123",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "Offer details not found" in response.json()["detail"]


def test_unfavorite_offer_not_favorited(client, mock_container, auth_headers):
    mock_container.user_offers_repo.get.return_value = None

    response = client.delete("/v2/offers/offer-123/favorite", headers=auth_headers)
    assert response.status_code == 404
    assert "Offer is not marked as favorite" in response.json()["detail"]


def test_unfavorite_offer_still_matched(
    client, mock_container, auth_headers, sample_domain_offer
):
    from core.models.user import User

    mock_container.user_offers_repo.get.return_value = {
        "user_id": "user-123",
        "offer_id": sample_domain_offer.offer_id,
        "cell_id": sample_domain_offer.cell_id,
        "favorited": True,
    }
    user = User(user_id="user-123")
    mock_container.users_repo = AsyncMock()
    mock_container.users_repo.get.return_value = user
    mock_container.offers_repo.get.return_value = sample_domain_offer
    # mock matching service filter to return the offer (meaning it matches)
    mock_container.matching_service = MagicMock()
    mock_container.matching_service._filter_offers_vectorized.return_value = [
        sample_domain_offer
    ]

    response = client.delete(
        f"/v2/offers/{sample_domain_offer.offer_id}/favorite", headers=auth_headers
    )
    assert response.status_code == 204
    mock_container.user_offers_repo.set_favorite.assert_called_once_with(
        "user-123", sample_domain_offer.offer_id, False
    )


def test_unfavorite_offer_no_longer_matched(
    client, mock_container, auth_headers, sample_domain_offer
):
    from core.models.user import User

    mock_container.user_offers_repo.get.return_value = {
        "user_id": "user-123",
        "offer_id": sample_domain_offer.offer_id,
        "cell_id": sample_domain_offer.cell_id,
        "favorited": True,
    }
    user = User(user_id="user-123")
    mock_container.users_repo = AsyncMock()
    mock_container.users_repo.get.return_value = user
    mock_container.offers_repo.get.return_value = sample_domain_offer
    # mock matching service filter to return empty list (no match)
    mock_container.matching_service = MagicMock()
    mock_container.matching_service._filter_offers_vectorized.return_value = []

    response = client.delete(
        f"/v2/offers/{sample_domain_offer.offer_id}/favorite", headers=auth_headers
    )
    assert response.status_code == 204
    mock_container.user_offers_repo.delete.assert_called_once_with(
        "user-123", sample_domain_offer.offer_id
    )


def test_get_favorites_feed_success(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.user_offers_repo.query_by_user.return_value = [
        {
            "user_id": "user-123",
            "offer_id": sample_domain_offer.offer_id,
            "cell_id": sample_domain_offer.cell_id,
            "favorited": True,
            "matched_at": "2026-06-24T12:00:00Z",
        }
    ]
    mock_container.offers_repo.get_batch.return_value = [sample_domain_offer]

    response = client.get("/v2/offers/favorites", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == sample_domain_offer.offer_id
    assert data["offers"][0]["favorited"] is True
    assert data["total_count"] == 1
