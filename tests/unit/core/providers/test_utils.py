from datetime import date
from decimal import Decimal

from core.models.common import BoardType, ProviderName
from core.models.offer import OfferMetadata, RawOffer, TuiMetadata, WakacjePlMetadata

from tests.unit.core.providers.utils import (
    board_label_matches,
    departure_city_label,
    hotel_title_token,
    verify_tui_offer_page,
    verify_wakacje_rendered_page,
)


def _sample_raw_offer(**overrides) -> RawOffer:
    defaults = {
        "provider": ProviderName.WAKACJE_PL,
        "external_offer_id": "351089",
        "hotel_name": "Jaz Lamaya Resort (ex Iberotel)",
        "location": "Egipt/Marsa El Alam/Madinat Coraya",
        "departure_airport": "GDN",
        "departure_date": date(2026, 7, 25),
        "return_date": date(2026, 7, 28),
        "duration": 3,
        "board": BoardType.ALL_INCLUSIVE,
        "stars": 5,
        "rating": Decimal("4.0"),
        "review_count": 10,
        "price_total": Decimal("5000.00"),
        "price_per_person": Decimal("2500.00"),
        "price_per_day": Decimal("833.33"),
        "referral_url": "https://www.wakacje.pl/oferty/example.html?selector",
        "available": True,
        "room_type": "Standard",
        "adults": 2,
        "children": 0,
        "metadata": OfferMetadata(
            wakacje_pl=WakacjePlMetadata(
                hotel_id=1,
                tour_operator_id=2,
                country_id=37,
                region_id=3,
                city_id=4,
                departure_city_id=5,
                service_id=1,
                departure_slug="z-gdanska",
                offer_page_path="/oferty/example.html",
                adults=2,
                children=0,
            )
        ),
    }
    defaults.update(overrides)
    return RawOffer(**defaults)


def test_hotel_title_token_strips_parenthetical():
    assert hotel_title_token("Jaz Lamaya Resort (ex Iberotel)") == "jaz"


def test_board_label_matches_all_inclusive():
    assert board_label_matches(BoardType.ALL_INCLUSIVE, "Pakiet All Inclusive")


def test_departure_city_label_uses_city_before_dash():
    departure_map = {"GDN": {"name": "Gdańsk", "id": 1, "slug": "z-gdanska"}}
    assert departure_city_label("GDN", departure_map) == "Gdańsk"


def test_verify_wakacje_rendered_page_passes_for_matching_text():
    offer: RawOffer = _sample_raw_offer()
    page_text = (
        "Jaz Lamaya Resort\n2 dorosłych\n25.07.2026 - 28.07.2026 / 3 nocy\n"
        "Gdańsk\nAll Inclusive\nCena razem\n5000"
    )
    failures = verify_wakacje_rendered_page(
        offer=offer,
        final_url="https://www.wakacje.pl/oferty/example-351089.html",
        page_text=page_text,
    )
    assert failures == []


def test_verify_tui_offer_page_parses_offer_code_data():
    offer: RawOffer = _sample_raw_offer(
        provider=ProviderName.TUI,
        external_offer_id="OFFER123",
        hotel_name="Hotel Kent",
        departure_airport="WAW",
        departure_date=date(2026, 7, 7),
        return_date=date(2026, 7, 12),
        board=BoardType.ALL_INCLUSIVE,
        metadata=OfferMetadata(tui=TuiMetadata(offer_code="OFFER123")),
    )
    html = """
    <html><head><title>Hotel Kent - TUI</title></head><body>
    <script id="__NEXT_DATA__" type="application/json">{
      "props": {
        "pageProps": {
          "initialPageData": {
            "offerCodeData": {
              "departureTime": "2026-07-07T10:10:00",
              "returnTime": "2026-07-12T03:40:00",
              "airportCode": "WAW",
              "boarding": "A"
            }
          }
        }
      }
    }</script></body></html>
    """
    failures = verify_tui_offer_page(
        offer=offer,
        final_url="https://www.tui.pl/example/OFFER123",
        html=html,
    )
    assert failures == []
