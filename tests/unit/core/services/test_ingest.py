from datetime import date, datetime, timezone
from decimal import Decimal
from pydantic import AnyHttpUrl, HttpUrl

from core.models.common import BoardType, ProviderName
from core.models.offer import (
    Offer,
    OfferMetadata,
    OfferSource,
    RawOffer,
    TuiMetadata,
    WakacjePlMetadata,
)
from core.services.ingest import (
    normalize_text,
    normalize_hotel,
    compute_offer_id,
    ingest_raw_offers,
    merge_existing_and_new_offer,
)


def create_test_raw_offer(
    provider: ProviderName,
    external_offer_id: str,
    price_total: float,
    hotel_name: str = "Test Hotel",
    location: str = "Grecja/Kreta/Chania",
    room_type: str = "Standard Room",
    adults: int = 2,
    children: int = 0,
    departure_date: date = date(2026, 6, 1),
    return_date: date = date(2026, 6, 8),
    duration: int = 7,
    board: BoardType = BoardType.ALL_INCLUSIVE,
    stars: int = 4,
    rating: float = 4.0,
    review_count: int = 100,
    wakacje_metadata: WakacjePlMetadata | None = None,
    tui_metadata: TuiMetadata | None = None,
) -> RawOffer:
    if provider == ProviderName.WAKACJE_PL and not wakacje_metadata:
        wakacje_metadata = WakacjePlMetadata(
            hotel_id=123,
            tour_operator_id=456,
            tour_op_code="TUI",
            country_id=1,
            region_id=2,
            city_id=3,
            departure_city_id=4,
            service_id=1,
            transport_id=1,
            departure_slug="z-warszawy",
            offer_page_path="/oferty/egipt/hurghada/hurghada/hotel-name-745287.html",
            adults=adults,
            children=children,
        )
    elif provider == ProviderName.TUI and not tui_metadata:
        tui_metadata = TuiMetadata(offer_code=external_offer_id)

    return RawOffer(
        provider=provider,
        external_offer_id=external_offer_id,
        hotel_name=hotel_name,
        location=location,
        departure_airport="WAW",
        departure_date=departure_date,
        return_date=return_date,
        duration=duration,
        board=board,
        stars=stars,
        rating=Decimal(str(rating)),
        review_count=review_count,
        price_total=Decimal(str(price_total)),
        price_per_person=(
            Decimal(str(price_total)) / (adults + children)
        ).quantize(Decimal("0.01")),
        price_per_day=(
            Decimal(str(price_total)) / duration / (adults + children)
        ).quantize(Decimal("0.01")),
        referral_url=AnyHttpUrl("https://example.com/ref"),
        available=True,
        room_type=room_type,
        adults=adults,
        children=children,
        metadata=OfferMetadata(
            wakacje_pl=wakacje_metadata,
            tui=tui_metadata,
        ),
    )


def create_test_offer(
    scored_offer: RawOffer,
    cell_id: str = "abc1234567890123",
    attractiveness_score: float = 0.8,
    scraped_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Offer:
    scraped_at = scraped_at or datetime.now(timezone.utc)
    updated_at = updated_at or datetime.now(timezone.utc)
    ttl = int(
        datetime.combine(
            scored_offer.departure_date, datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
    )

    offer_id = compute_offer_id(scored_offer)

    return Offer(
        **scored_offer.model_dump(),
        cell_id=cell_id,
        offer_id=offer_id,
        attractiveness_score=attractiveness_score,
        share_url=HttpUrl("https://wakacje-travelis.pl/offer/dummy/dummy"),
        scraped_at=scraped_at,
        updated_at=updated_at,
        ttl=ttl,
    )


def test_normalize_text():
    assert normalize_text("Hotel SPA & Wellness Łeba") == "hotel spa wellness leba"
    assert normalize_text("   Grecja /   Kreta (Chania)   ") == "grecja kreta chania"
    assert normalize_text("Straße") == "strasse"
    assert normalize_text("Hotel's Grand!") == "hotels grand"


def test_normalize_hotel():
    assert (
        normalize_hotel("Hotel SPA Łeba", "Polska", "Pomorze")
        == "hotel spa leba:polska:pomorze"
    )


def test_compute_offer_id():
    raw_offer: RawOffer = create_test_raw_offer(
        ProviderName.WAKACJE_PL, "ext-1", 1000.00
    )
    expected_id = compute_offer_id(raw_offer)
    assert len(expected_id) == 32
    int(expected_id, 16)


def test_ingest_raw_offers_collapsing():
    # Setup two offers with same fingerprint (same hotel, dates, occupancy, room type etc)
    o1 = create_test_raw_offer(
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="ext-cheap",
        price_total=1000.00,
        hotel_name="Grand Hotel",
    )
    o2 = create_test_raw_offer(
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="ext-expensive",
        price_total=1200.00,
        hotel_name="Grand Hotel",
    )
    # A different offer (different hotel name)
    o3 = create_test_raw_offer(
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="ext-other",
        price_total=1500.00,
        hotel_name="Other Hotel",
    )

    results = ingest_raw_offers([o1, o2, o3])

    assert len(results) == 2

    grand_hotel_results = [r for r in results if r.hotel_name == "Grand Hotel"]
    assert len(grand_hotel_results) == 1
    winner = grand_hotel_results[0]
    assert winner.external_offer_id == "ext-cheap"
    assert winner.price_total == Decimal("1000.00")

    sources = winner.metadata.sources
    assert len(sources) == 2

    cheap_src = next(s for s in sources if s.external_offer_id == "ext-cheap")
    assert cheap_src.price_total == Decimal("1000.00")

    exp_src = next(s for s in sources if s.external_offer_id == "ext-expensive")
    assert exp_src.price_total == Decimal("1200.00")


def test_merge_existing_and_new_offer_same_provider():
    t_existing = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 6, 17, 18, 0, 0, tzinfo=timezone.utc)

    raw_existing = create_test_raw_offer(ProviderName.WAKACJE_PL, "ext-1", 1000.00)
    existing_offer: Offer = create_test_offer(
        raw_existing, scraped_at=t_existing, updated_at=t_existing
    )

    raw_new = create_test_raw_offer(ProviderName.WAKACJE_PL, "ext-1", 1100.00)
    new_offer: Offer = create_test_offer(raw_new, scraped_at=t_new, updated_at=t_new)

    merged = merge_existing_and_new_offer(existing_offer, new_offer)

    assert merged.price_total == Decimal("1100.00")
    assert merged.scraped_at == t_new
    assert merged.updated_at == t_new
    assert len(merged.metadata.sources) == 1
    assert merged.metadata.sources[0].price_total == Decimal("1100.00")


def test_merge_existing_and_new_offer_cross_provider_new_wins():
    t_existing = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 6, 17, 18, 0, 0, tzinfo=timezone.utc)

    raw_existing = create_test_raw_offer(ProviderName.TUI, "tui-code", 1200.00)
    existing_offer: Offer = create_test_offer(
        raw_existing, scraped_at=t_existing, updated_at=t_existing
    )

    raw_new = create_test_raw_offer(ProviderName.WAKACJE_PL, "wakacje-code", 1100.00)
    new_offer: Offer = create_test_offer(raw_new, scraped_at=t_new, updated_at=t_new)

    merged = merge_existing_and_new_offer(existing_offer, new_offer)

    assert merged.provider == ProviderName.WAKACJE_PL
    assert merged.external_offer_id == "wakacje-code"
    assert merged.price_total == Decimal("1100.00")
    assert merged.scraped_at == t_new
    assert merged.updated_at == t_new

    assert merged.metadata.tui is not None
    assert merged.metadata.wakacje_pl is not None

    sources = merged.metadata.sources
    assert len(sources) == 2
    assert any(
        s.provider == ProviderName.TUI and s.price_total == Decimal("1200.00")
        for s in sources
    )
    assert any(
        s.provider == ProviderName.WAKACJE_PL and s.price_total == Decimal("1100.00")
        for s in sources
    )


def test_merge_existing_and_new_offer_cross_provider_existing_wins():
    t_existing = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 6, 17, 18, 0, 0, tzinfo=timezone.utc)

    raw_existing = create_test_raw_offer(ProviderName.TUI, "tui-code", 1000.00)
    existing_offer: Offer = create_test_offer(
        raw_existing, scraped_at=t_existing, updated_at=t_existing
    )

    raw_new = create_test_raw_offer(ProviderName.WAKACJE_PL, "wakacje-code", 1100.00)
    new_offer: Offer = create_test_offer(raw_new, scraped_at=t_new, updated_at=t_new)

    merged = merge_existing_and_new_offer(existing_offer, new_offer)

    assert merged.provider == ProviderName.TUI
    assert merged.external_offer_id == "tui-code"
    assert merged.price_total == Decimal("1000.00")
    assert merged.scraped_at == t_new
    assert merged.updated_at == t_new

    assert merged.metadata.tui is not None
    assert merged.metadata.wakacje_pl is not None

    sources = merged.metadata.sources
    assert len(sources) == 2


def test_merge_existing_and_new_offer_pruning():
    t_existing = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 6, 17, 18, 0, 0, tzinfo=timezone.utc)

    raw_existing = create_test_raw_offer(
        ProviderName.WAKACJE_PL, "wakacje-active", 1000.00
    )
    existing_offer: Offer = create_test_offer(
        raw_existing, scraped_at=t_existing, updated_at=t_existing
    )

    existing_offer.metadata.sources = [
        OfferSource(
            provider=ProviderName.WAKACJE_PL,
            external_offer_id="wakacje-active",
            price_total=Decimal("1000.00"),
        ),
        OfferSource(
            provider=ProviderName.WAKACJE_PL,
            external_offer_id="wakacje-stale",
            price_total=Decimal("1100.00"),
        ),
        OfferSource(
            provider=ProviderName.TUI,
            external_offer_id="tui-other",
            price_total=Decimal("1200.00"),
        ),
    ]
    existing_offer.metadata.tui = TuiMetadata(offer_code="tui-other")

    raw_new = create_test_raw_offer(ProviderName.WAKACJE_PL, "wakacje-active", 1050.00)
    new_offer: Offer = create_test_offer(raw_new, scraped_at=t_new, updated_at=t_new)
    new_offer.metadata.sources = [
        OfferSource(
            provider=ProviderName.WAKACJE_PL,
            external_offer_id="wakacje-active",
            price_total=Decimal("1050.00"),
        ),
    ]

    merged = merge_existing_and_new_offer(existing_offer, new_offer)

    sources = merged.metadata.sources
    assert len(sources) == 2

    active_src = next(s for s in sources if s.external_offer_id == "wakacje-active")
    assert active_src.price_total == Decimal("1050.00")

    tui_src = next(s for s in sources if s.external_offer_id == "tui-other")
    assert tui_src.price_total == Decimal("1200.00")

    assert not any(s.external_offer_id == "wakacje-stale" for s in sources)

    assert merged.metadata.tui is not None
    assert merged.metadata.wakacje_pl is not None
