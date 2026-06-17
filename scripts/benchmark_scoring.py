import math
import time
import random
import numpy as np
import pandas as pd
from datetime import date
from decimal import Decimal
from typing import Sequence

from core.models.common import BoardType, ProviderName
from core.models.offer import OfferMetadata, RawOffer, ScoredOffer
from core.services.scoring.config import StatisticalScorerConfig
from core.services.scoring.statistical import StatisticalOfferScorer


class NumpyOfferScorer:
    """Numpy-vectorized version of the StatisticalOfferScorer."""
    def __init__(self, config: StatisticalScorerConfig | None = None):
        self.config = config or StatisticalScorerConfig()

    def score(self, offers: Sequence[RawOffer]) -> list[ScoredOffer]:
        if not offers:
            return []

        n = len(offers)
        
        # O(N) extraction loop - unavoidable with Pydantic models
        prices = np.zeros(n, dtype=np.float64)
        ratings = np.zeros(n, dtype=np.float64)
        log_reviews = np.zeros(n, dtype=np.float64)
        
        for i, offer in enumerate(offers):
            prices[i] = float(offer.price_per_day_one_person)
            ratings[i] = float(offer.rating)
            log_reviews[i] = math.log1p(offer.review_count)
            
        min_price = np.min(prices)
        max_price = np.max(prices)
        min_rating = np.min(ratings)
        max_rating = np.max(ratings)
        min_log_reviews = np.min(log_reviews)
        max_log_reviews = np.max(log_reviews)

        # Stage 1
        if n < self.config.small_sample_threshold:
            keep_count = max(1, math.ceil(n * self.config.small_sample_keep_ratio))
            sorted_indices = np.argsort(prices)
            passing_indices = sorted_indices[:keep_count]
        else:
            mean_price = np.mean(prices)
            stddev = np.std(prices)
            
            if stddev > 0:
                z_scores = (prices - mean_price) / stddev
            else:
                z_scores = np.zeros(n, dtype=np.float64)
                
            passing_mask = z_scores <= self.config.z_threshold
            passing_indices = np.where(passing_mask)[0]
            
            # Apply z-score to metadata
            for i in range(n):
                offers[i].metadata.price_z_score = float(z_scores[i])

        if len(passing_indices) == 0:
            return []

        # Stage 2
        passing_prices = prices[passing_indices]
        passing_ratings = ratings[passing_indices]
        passing_log_reviews = log_reviews[passing_indices]

        price_norm = (max_price - passing_prices) / (max_price - min_price) if max_price > min_price else np.ones(len(passing_indices))
        rating_norm = (passing_ratings - min_rating) / (max_rating - min_rating) if max_rating > min_rating else np.ones(len(passing_indices))
        reviews_norm = (passing_log_reviews - min_log_reviews) / (max_log_reviews - min_log_reviews) if max_log_reviews > min_log_reviews else np.ones(len(passing_indices))

        composites = (
            self.config.weight_price * price_norm +
            self.config.weight_rating * rating_norm +
            self.config.weight_reviews * reviews_norm
        )

        results = []
        for idx, composite in zip(passing_indices, composites):
            offer = offers[idx]
            scored_offer = ScoredOffer(
                **offer.model_dump(),
                attractiveness_score=float(composite)
            )
            results.append(scored_offer)

        return results

        return results


class PandasOfferScorer:
    """Pandas-vectorized version of the StatisticalOfferScorer."""
    def __init__(self, config: StatisticalScorerConfig | None = None):
        self.config = config or StatisticalScorerConfig()

    def score(self, offers: Sequence[RawOffer]) -> list[ScoredOffer]:
        if not offers:
            return []

        n = len(offers)
        
        # O(N) extraction loop - unavoidable with Pydantic models
        df = pd.DataFrame({
            "price": [float(o.price_per_day_one_person) for o in offers],
            "rating": [float(o.rating) for o in offers],
            "reviews": [o.review_count for o in offers]
        })
        df["log_reviews"] = np.log1p(df["reviews"])
        
        min_price = df["price"].min()
        max_price = df["price"].max()
        min_rating = df["rating"].min()
        max_rating = df["rating"].max()
        min_log_reviews = df["log_reviews"].min()
        max_log_reviews = df["log_reviews"].max()

        # Stage 1
        if n < self.config.small_sample_threshold:
            keep_count = max(1, math.ceil(n * self.config.small_sample_keep_ratio))
            passing_df = df.nsmallest(keep_count, "price")
        else:
            mean_price = df["price"].mean()
            stddev = df["price"].std(ddof=0) # ddof=0 to match numpy/math exact population stddev
            
            if stddev > 0:
                df["z_score"] = (df["price"] - mean_price) / stddev
            else:
                df["z_score"] = 0.0
                
            passing_df = df[df["z_score"] <= self.config.z_threshold]
            
            # Apply z-score to metadata
            for i, row in df.iterrows():
                offers[i].metadata.price_z_score = float(row["z_score"])

        if passing_df.empty:
            return []

        # Stage 2
        price_norm = 1.0 if max_price == min_price else (max_price - passing_df["price"]) / (max_price - min_price)
        rating_norm = 1.0 if max_rating == min_rating else (passing_df["rating"] - min_rating) / (max_rating - min_rating)
        reviews_norm = 1.0 if max_log_reviews == min_log_reviews else (passing_df["log_reviews"] - min_log_reviews) / (max_log_reviews - min_log_reviews)

        passing_df["composite"] = (
            self.config.weight_price * price_norm +
            self.config.weight_rating * rating_norm +
            self.config.weight_reviews * reviews_norm
        )

        results = []
        for idx, row in passing_df.iterrows():
            offer = offers[idx]
            scored_offer = ScoredOffer(
                **offer.model_dump(),
                attractiveness_score=float(row["composite"])
            )
            results.append(scored_offer)

        return results

def create_mock_offer(
    price_total: int,
    rating: float,
    review_count: int,
    duration: int = 7,
    adults: int = 2,
    children: int = 0,
) -> RawOffer:
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
        rating=rating,
        review_count=review_count,
        price_total=Decimal(price_total),
        price_per_day_one_person=round(Decimal(price_total) / duration / (adults + children), 2),
        referral_url="https://example.com",
        available=True,
        room_type="Standard",
        metadata=OfferMetadata(),
    )


def main():
    sample_size = 10000
    print(f"Generating {sample_size} mock offers...")
    offers = []
    for _ in range(sample_size):
        offers.append(
            create_mock_offer(
                price_total=random.randint(1000, 5000),
                rating=round(random.uniform(2.0, 5.0), 1),
                review_count=random.randint(0, 2000),
            )
        )
        
    print("\nBenchmarking Pure Python Scorer...")
    python_scorer = StatisticalOfferScorer()
    
    # Warm-up (to pre-load any lazy imports or JIT if applicable)
    # python_scorer.score(offers[:10])
    
    start = time.perf_counter()
    python_res = python_scorer.score(offers)
    python_time = time.perf_counter() - start
    
    print("\nBenchmarking Numpy Scorer...")
    numpy_scorer = NumpyOfferScorer()
    
    # Warm-up (especially important for numpy to load C-extensions)
    # numpy_scorer.score(offers[:10])
    
    start = time.perf_counter()
    numpy_res = numpy_scorer.score(offers)
    numpy_time = time.perf_counter() - start
    
    print("\nBenchmarking Pandas Scorer...")
    pandas_scorer = PandasOfferScorer()
    
    # Warm-up (pandas init can be slow)
    # pandas_scorer.score(offers[:10])
    
    start = time.perf_counter()
    pandas_res = pandas_scorer.score(offers)
    pandas_time = time.perf_counter() - start
    
    print(f"\n--- Results ---")
    print(f"Pure Python: {python_time:.4f} seconds ({len(python_res)} passed)")
    print(f"Numpy:       {numpy_time:.4f} seconds ({len(numpy_res)} passed)")
    print(f"Pandas:      {pandas_time:.4f} seconds ({len(pandas_res)} passed)")
    
    times = {
        "Pure Python": python_time,
        "Numpy": numpy_time,
        "Pandas": pandas_time
    }
    fastest = min(times, key=times.get)
    print(f"\n{fastest} was the fastest!")


if __name__ == "__main__":
    main()
