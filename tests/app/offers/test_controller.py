import base64
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_container
from app.main import app
from core.models.common import BoardType, ProviderName
from core.models.offer import Offer, OfferMetadata, OfferSource, TuiMetadata


@pytest.fixture
def mock_container():
    c = MagicMock()
    c.feed_repo = AsyncMock()
    c.user_offers_repo = AsyncMock()
    c.offers_repo = AsyncMock()
    c.settings = MagicMock()
    return c


@pytest.fixture
def client(mock_container):
    app.dependency_overrides[get_container] = lambda: mock_container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    payload = {"sub": "user-123"}
    token = jwt.encode(payload, "a" * 32, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


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

    response = client.get("/api/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["offers"] == []
    assert data["next_cursor"] is None
    assert data["feed_version"] == 1


def test_get_offers_cached_feed(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 42
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True

    offer_id = sample_domain_offer.offer_id
    mock_container.feed_repo.get_page.return_value = [offer_id]
    mock_container.user_offers_repo.get.return_value = {
        "user_id": "user-123",
        "offer_id": offer_id,
        "cell_id": "cell-1",
    }
    mock_container.offers_repo.get.return_value = sample_domain_offer

    response = client.get("/api/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == offer_id
    assert data["feed_version"] == 42
    assert data["next_cursor"] is None


def test_get_offers_build_zset(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 1
    mock_container.feed_repo.get_or_build_sort_zset.return_value = False

    offer_id = sample_domain_offer.offer_id
    mock_container.user_offers_repo.query_by_user.return_value = [
        {"offer_id": offer_id, "cell_id": "cell-1"}
    ]
    mock_container.offers_repo.get.return_value = sample_domain_offer

    mock_container.feed_repo.get_page.return_value = [offer_id]
    mock_container.user_offers_repo.get.return_value = {
        "offer_id": offer_id,
        "cell_id": "cell-1",
    }

    response = client.get("/api/v2/offers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["offers"]) == 1
    assert data["offers"][0]["offer_id"] == offer_id

    # Assert ZSET was built
    mock_container.feed_repo.add_to_sort_zset.assert_called_once()


def test_get_offers_outdated_cursor_resets(
    client, mock_container, auth_headers, sample_domain_offer
):
    mock_container.feed_repo.get_feed_version.return_value = 50
    mock_container.feed_repo.get_or_build_sort_zset.return_value = True
    mock_container.feed_repo.get_page.return_value = [sample_domain_offer.offer_id]
    mock_container.user_offers_repo.get.return_value = {
        "offer_id": sample_domain_offer.offer_id,
        "cell_id": "cell-1",
    }
    mock_container.offers_repo.get.return_value = sample_domain_offer

    # Cursor with version 49
    cursor_data = {"offset": 20, "feed_version": 49}
    cursor_str = base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode(
        "utf-8"
    )

    response = client.get(f"/api/v2/offers?cursor={cursor_str}", headers=auth_headers)
    assert response.status_code == 200

    # It should query page 1 (offset=0, limit=20) instead of offset 20 from cursor due to mismatch
    mock_container.feed_repo.get_page.assert_called_once_with(
        user_id="user-123",
        field="attractiveness",
        order="desc",
        version=50,
        offset=0,
        limit=20,
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

    response = client.get(f"/api/v2/offers/{offer_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["offer_id"] == offer_id
    assert data["hotel_name"] == "Test Hotel"


def test_get_offer_detail_not_matched(client, mock_container, auth_headers):
    mock_container.user_offers_repo.get.return_value = None

    response = client.get("/api/v2/offers/some-offer-id", headers=auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_shared_offer_detail(client, mock_container, sample_domain_offer):
    offer_id = sample_domain_offer.offer_id
    mock_container.offers_repo.get.return_value = sample_domain_offer

    # Unauthenticated request
    response = client.get(f"/api/v2/offers/cell-123/{offer_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["offer_id"] == offer_id


def test_get_shared_offer_detail_not_found(client, mock_container):
    mock_container.offers_repo.get.return_value = None

    response = client.get("/api/v2/offers/cell-123/some-offer-id")
    assert response.status_code == 404
