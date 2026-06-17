import math
from typing import Sequence

from core.models.offer import RawOffer, ScoredOffer
from core.services.scoring.base import OfferScorer
from core.services.scoring.config import StatisticalScorerConfig


class StatisticalOfferScorer(OfferScorer):
    def __init__(self, config: StatisticalScorerConfig | None = None):
        self.config = config or StatisticalScorerConfig()

    def score(self, offers: Sequence[RawOffer]) -> list[ScoredOffer]:
        if not offers:
            return []

        n = len(offers)
        
        # 1. Extract and calculate base metrics for the entire comparison pool
        pool_metrics = []
        for offer in offers:
            # price_total is a Decimal, cast to float for math
            price_pp = float(offer.price_per_day_one_person)
            log_reviews = math.log1p(offer.review_count)
            pool_metrics.append({
                "offer": offer,
                "price_pp": price_pp,
                "rating": float(offer.rating),
                "log_reviews": log_reviews,
            })

        # 2. Find min/max for normalization across the entire pool
        min_price = min(m["price_pp"] for m in pool_metrics)
        max_price = max(m["price_pp"] for m in pool_metrics)
        
        min_rating = min(m["rating"] for m in pool_metrics)
        max_rating = max(m["rating"] for m in pool_metrics)
        
        min_log_reviews = min(m["log_reviews"] for m in pool_metrics)
        max_log_reviews = max(m["log_reviews"] for m in pool_metrics)

        # 3. Stage 1: Z-score gate or small sample fallback
        passing_metrics = []
        
        if n < self.config.small_sample_threshold:
            # Small sample fallback: bypass Z-score, take top N cheapest
            keep_count = max(1, math.ceil(n * self.config.small_sample_keep_ratio))
            # Set Z-score to None since it's not applicable
            for m in pool_metrics:
                m["offer"].metadata.price_z_score = None
            
            # Sort by price ascending
            pool_metrics.sort(key=lambda x: x["price_pp"])
            passing_metrics = pool_metrics[:keep_count]
        else:
            # Calculate Z-scores
            mean_price = sum(m["price_pp"] for m in pool_metrics) / n
            variance = sum((m["price_pp"] - mean_price) ** 2 for m in pool_metrics) / n
            stddev = math.sqrt(variance)
            
            for m in pool_metrics:
                z = (m["price_pp"] - mean_price) / stddev if stddev > 0.0 else 0.0
                m["offer"].metadata.price_z_score = z
                
                if z <= self.config.z_threshold:
                    passing_metrics.append(m)

        # 4. Stage 2: Composite Score
        results = []
        for m in passing_metrics:
            # Price normalization: 1.0 is best (lowest price)
            if max_price == min_price:
                price_norm = 1.0
            else:
                price_norm = (max_price - m["price_pp"]) / (max_price - min_price)
                
            # Rating normalization: 1.0 is best (highest rating)
            if max_rating == min_rating:
                rating_norm = 1.0
            else:
                rating_norm = (m["rating"] - min_rating) / (max_rating - min_rating)
                
            # Reviews normalization: 1.0 is best (highest log_reviews)
            if max_log_reviews == min_log_reviews:
                reviews_norm = 1.0
            else:
                reviews_norm = (m["log_reviews"] - min_log_reviews) / (max_log_reviews - min_log_reviews)
                
            composite = (
                self.config.weight_price * price_norm +
                self.config.weight_rating * rating_norm +
                self.config.weight_reviews * reviews_norm
            )
            
            scored_offer = ScoredOffer(
                **m["offer"].model_dump(),
                attractiveness_score=composite
            )
            results.append(scored_offer)

        return results
