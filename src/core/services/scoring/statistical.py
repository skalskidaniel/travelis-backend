import math
from typing import Sequence
import numpy as np

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

        prices = np.zeros(n, dtype=np.float64)
        ratings = np.zeros(n, dtype=np.float64)
        log_reviews = np.zeros(n, dtype=np.float64)

        for i, offer in enumerate(offers):
            prices[i] = float(offer.price_per_day)
            ratings[i] = float(offer.rating)
            log_reviews[i] = math.log1p(offer.review_count)

        min_price = np.min(prices)
        max_price = np.max(prices)
        min_rating = np.min(ratings)
        max_rating = np.max(ratings)
        min_log_reviews = np.min(log_reviews)
        max_log_reviews = np.max(log_reviews)

        # Stage 1
        # noinspection DuplicatedCode
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

            for i in range(n):
                offers[i].metadata.price_z_score = float(z_scores[i])

        if len(passing_indices) == 0:
            return []

        # Stage 2
        passing_prices = prices[passing_indices]
        passing_ratings = ratings[passing_indices]
        passing_log_reviews = log_reviews[passing_indices]

        price_norm = (
            (max_price - passing_prices) / (max_price - min_price)
            if max_price > min_price
            else np.ones(len(passing_indices))
        )
        rating_norm = (
            (passing_ratings - min_rating) / (max_rating - min_rating)
            if max_rating > min_rating
            else np.ones(len(passing_indices))
        )
        reviews_norm = (
            (passing_log_reviews - min_log_reviews)
            / (max_log_reviews - min_log_reviews)
            if max_log_reviews > min_log_reviews
            else np.ones(len(passing_indices))
        )

        composites = (
            self.config.weight_price * price_norm
            + self.config.weight_rating * rating_norm
            + self.config.weight_reviews * reviews_norm
        )

        results = []
        for idx, composite in zip(passing_indices, composites):
            offer = offers[idx]
            scored_offer = ScoredOffer(
                **offer.model_dump(), attractiveness_score=float(composite)
            )
            results.append(scored_offer)

        return results
