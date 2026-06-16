from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from core.models.offer import Offer, OfferMetadata, TuiMetadata
from core.models.common import BoardType, ProviderName
from core.exceptions.provider import DateMismatchException, DurationMismatchException


@pytest.fixture
def valid_offer_kwargs():
    return {
        "provider": ProviderName.TUI,
        "external_offer_id": "TUI-OFFER-123",
        "hotel_name": "Grand Resort & Spa",
        "location": "Grecja/Kreta/Chania",
        "departure_airport": "WAW",
        "departure_date": date(2026, 7, 12),
        "return_date": date(2026, 7, 19),
        "duration": 7,
        "board": BoardType.ALL_INCLUSIVE,
        "stars": 5,
        "rating": Decimal("4.8"),
        "review_count": 150,
        "price_total": Decimal("4500.00"),
        "price_per_day_one_person": Decimal("642.86"),
        "referral_url": "https://www.tui.pl/details-gre-123",
        "available": True,
        "room_type": "Superior Double Room",
        "metadata": OfferMetadata(
            tui=TuiMetadata(offer_code="TUI-OFFER-123"),
        ),
        "cell_id": "1234567890abcdef",
        "offer_id": "abcdefabcdefabcdefabcdefabcdef12",
        "attractiveness_score": 0.95,
        "share_url": "https://wakacje-travelis.pl/offer/1234567890abcdef/abcdefabcdefabcdefabcdefabcdef12",
        "scraped_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "ttl": 1783814400,
    }


def test_referral_url_appending_no_query_params(valid_offer_kwargs):
    valid_offer_kwargs["referral_url"] = "https://www.tui.pl/details-gre-123"
    offer = Offer(**valid_offer_kwargs)

    expected_url = (
        "https://www.tui.pl/details-gre-123"
        "?utm_source=travellead&utm_medium=cps&utm_campaign=2933-t-HolidayPicker&a_cid=11111111&a_aid=2933"
    )
    assert str(offer.referral_url) == expected_url


def test_referral_url_appending_with_existing_query_params(valid_offer_kwargs):
    valid_offer_kwargs["referral_url"] = (
        "https://www.tui.pl/details-gre-123?foo=bar&baz=123"
    )
    offer = Offer(**valid_offer_kwargs)

    url_str = str(offer.referral_url)
    assert "foo=bar" in url_str
    assert "baz=123" in url_str
    assert "utm_source=travellead" in url_str
    assert "utm_medium=cps" in url_str
    assert "utm_campaign=2933-t-HolidayPicker" in url_str
    assert "a_cid=11111111" in url_str
    assert "a_aid=2933" in url_str


def test_referral_url_appending_overwrites_existing_referral_params(valid_offer_kwargs):
    valid_offer_kwargs["referral_url"] = (
        "https://www.tui.pl/details-gre-123?utm_source=wrong&utm_medium=bad&foo=bar"
    )
    offer = Offer(**valid_offer_kwargs)

    url_str = str(offer.referral_url)
    assert "foo=bar" in url_str
    assert "utm_source=travellead" in url_str
    assert "utm_medium=cps" in url_str
    assert "utm_source=wrong" not in url_str
    assert "utm_medium=bad" not in url_str


def test_referral_url_no_modification_when_already_correct(valid_offer_kwargs):
    correct_url = (
        "https://www.tui.pl/details-gre-123"
        "?utm_source=travellead&utm_medium=cps&utm_campaign=2933-t-HolidayPicker&a_cid=11111111&a_aid=2933"
    )
    valid_offer_kwargs["referral_url"] = correct_url
    offer = Offer(**valid_offer_kwargs)

    assert str(offer.referral_url) == correct_url


def test_share_url_prefix_validation(valid_offer_kwargs):
    valid_offer_kwargs["share_url"] = "https://wrong-domain.com/offer/123"
    with pytest.raises(ValidationError) as exc_info:
        Offer(**valid_offer_kwargs)
    assert "share_url must start with" in str(exc_info.value)


def test_date_mismatch_validation(valid_offer_kwargs):
    valid_offer_kwargs["departure_date"] = date(2026, 7, 19)
    valid_offer_kwargs["return_date"] = date(2026, 7, 12)
    valid_offer_kwargs["duration"] = 7

    with pytest.raises(
        DateMismatchException, match="return_date must be on or after departure_date"
    ):
        Offer(**valid_offer_kwargs)


def test_duration_mismatch_validation(valid_offer_kwargs):
    valid_offer_kwargs["departure_date"] = date(2026, 7, 12)
    valid_offer_kwargs["return_date"] = date(2026, 7, 19)
    valid_offer_kwargs["duration"] = 5

    with pytest.raises(
        DurationMismatchException, match="duration must equal the number of nights"
    ):
        Offer(**valid_offer_kwargs)


def test_wakacje_pl_requires_wakacje_metadata(valid_offer_kwargs):
    valid_offer_kwargs["provider"] = ProviderName.WAKACJE_PL
    valid_offer_kwargs["external_offer_id"] = "WAK-123"
    valid_offer_kwargs["metadata"] = OfferMetadata(wakacje_pl=None)

    with pytest.raises(
        ValidationError, match="metadata.wakacje is required for wakacje offers"
    ):
        Offer(**valid_offer_kwargs)


def test_tui_requires_tui_metadata(valid_offer_kwargs):
    valid_offer_kwargs["provider"] = ProviderName.TUI
    valid_offer_kwargs["metadata"] = OfferMetadata(tui=None)

    with pytest.raises(
        ValidationError, match="metadata.tui is required for tui offers"
    ):
        Offer(**valid_offer_kwargs)


def test_tui_requires_external_id_to_match_metadata_code(valid_offer_kwargs):
    valid_offer_kwargs["provider"] = ProviderName.TUI
    valid_offer_kwargs["external_offer_id"] = "TUI-OFFER-123"
    valid_offer_kwargs["metadata"] = OfferMetadata(
        tui=TuiMetadata(offer_code="DIFFERENT-CODE"),
    )

    with pytest.raises(
        ValidationError, match="provider_id must match metadata.tui.offer_code"
    ):
        Offer(**valid_offer_kwargs)
