from datetime import date
from decimal import Decimal
import time
import random

import pytest
from pydantic import AnyHttpUrl

from core.models.common import BoardType, ProviderName
from core.models.offer import OfferMetadata, RawOffer, ScoredOffer
from core.services.scoring import get_scorer, StatisticalScorerConfig


def create_mock_offer(
    price_total: int,
    rating: float,
    review_count: int,
    duration: int = 7,
    adults: int = 2,
    children: int = 0,
) -> RawOffer:
    """Helper to create a minimal RawOffer for scoring tests."""
    return RawOffer(
        provider=ProviderName.WAKACJE_PL,
        external_offer_id="test-123",
        hotel_name="Test Hotel",
        location="Grecja/Kreta/Chania",
        departure_airport="WAW",
        departure_date=date(2026, 6, 1),
        return_date=date(2026, 6, 8),
        duration=duration,
        board=BoardType.ALL_INCLUSIVE,
        stars=4,
        rating=Decimal(str(rating)),
        review_count=review_count,
        price_total=Decimal(price_total),
        price_per_person=round(Decimal(price_total) / (adults + children), 2),
        price_per_day=round(Decimal(price_total) / duration / (adults + children), 2),
        referral_url=AnyHttpUrl("https://example.com"),
        available=True,
        room_type="Standard",
        adults=adults,
        children=children,
        metadata=OfferMetadata(),
    )


def test_factory_returns_statistical_scorer():
    scorer = get_scorer("statistical")
    assert scorer.__class__.__name__ == "StatisticalOfferScorer"


def test_factory_raises_value_error_for_unknown():
    with pytest.raises(ValueError, match="Unknown scoring version"):
        get_scorer("unknown_version")


def test_small_sample_fallback():
    config = StatisticalScorerConfig(
        small_sample_threshold=30, small_sample_keep_ratio=0.5
    )
    scorer = get_scorer("statistical", config=config)

    offers: list[RawOffer] = [
        create_mock_offer(price_total=1000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
        create_mock_offer(price_total=3000, rating=4.0, review_count=10),
        create_mock_offer(price_total=4000, rating=4.0, review_count=10),
        create_mock_offer(price_total=5000, rating=4.0, review_count=10),
    ]

    results = scorer.score(offers)

    assert len(results) == 3
    passing_prices = [res.price_total for res in results]
    assert sorted(passing_prices) == [Decimal(1000), Decimal(2000), Decimal(3000)]

    assert all(res.metadata.price_z_score is None for res in results)


def test_z_score_gate():
    config = StatisticalScorerConfig(small_sample_threshold=5, z_threshold=-1.0)
    scorer = get_scorer("statistical", config=config)

    # Mean: 1833.33, Stddev: ~372.67
    # 1000 z-score = (1000 - 1833.33) / 372.67 = -2.23 (passes z <= -1.0)
    # 2000 z-score = (2000 - 1833.33) / 372.67 = 0.44 (fails)
    offers = [
        create_mock_offer(price_total=1000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
        create_mock_offer(price_total=2000, rating=4.0, review_count=10),
    ]

    results = scorer.score(offers)

    assert len(results) == 1
    passed_offer: ScoredOffer = results[0]
    assert passed_offer.price_total == Decimal(1000)
    assert passed_offer.metadata.price_z_score is not None
    assert passed_offer.metadata.price_z_score <= -1.0


def test_composite_score_ranking():
    config = StatisticalScorerConfig(
        small_sample_threshold=10, small_sample_keep_ratio=1.0
    )
    scorer = get_scorer("statistical", config=config)

    offers: list[RawOffer] = [
        # Offer A: Best price, high rating, medium reviews
        create_mock_offer(price_total=1000, rating=4.5, review_count=500),
        # Offer B: Worst price, best rating, high reviews
        create_mock_offer(price_total=3000, rating=4.8, review_count=1200),
        # Offer C: Medium price, worst rating, low reviews
        create_mock_offer(price_total=2000, rating=3.9, review_count=80),
    ]

    results = scorer.score(offers)
    assert len(results) == 3

    scores_by_price = {res.price_total: res.attractiveness_score for res in results}

    # Offer A should have a very high score (best price = 1.0 norm, good rating, good reviews)
    score_a = scores_by_price[Decimal(1000)]
    # Offer C has medium price, worst rating (0.0 norm) and worst reviews (0.0 norm)
    score_c = scores_by_price[Decimal(2000)]

    assert score_a > score_c


def test_normalization_division_by_zero_handling():
    config = StatisticalScorerConfig(
        small_sample_threshold=10, small_sample_keep_ratio=1.0
    )
    scorer = get_scorer("statistical", config=config)

    offers: list[RawOffer] = [
        create_mock_offer(price_total=2000, rating=4.0, review_count=100),
        create_mock_offer(price_total=2000, rating=4.0, review_count=100),
        create_mock_offer(price_total=2000, rating=4.0, review_count=100),
    ]

    results = scorer.score(offers)
    assert len(results) == 3

    for offer in results:
        assert offer.attractiveness_score == 1.0


def test_performance_large_pool():
    config = StatisticalScorerConfig(small_sample_threshold=30, z_threshold=-1.0)
    scorer = get_scorer("statistical", config=config)

    offers: list[RawOffer] = []
    for i in range(10000):
        price = random.randint(1000, 5000)
        rating = round(random.uniform(2.0, 5.0), 1)
        reviews = random.randint(0, 2000)

        offers.append(
            create_mock_offer(
                price_total=price,
                rating=rating,
                review_count=reviews,
                duration=7,
                adults=2,
                children=0,
            )
        )

    start_time = time.perf_counter()
    results = scorer.score(offers)
    end_time = time.perf_counter()

    execution_time_seconds = end_time - start_time

    assert execution_time_seconds < 0.2, (
        f"Scoring 10000 offers took too long: {execution_time_seconds:.4f}s"
    )

    assert len(results) > 0
