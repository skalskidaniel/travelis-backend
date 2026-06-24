from pydantic import BaseModel, Field


class StatisticalScorerConfig(BaseModel):
    """Configuration for the Statistical Offer Scorer."""

    z_threshold: float = Field(
        default=-1.2,
        description="Z-score threshold for Stage 1. Offers with z <= threshold pass.",
    )
    small_sample_threshold: int = Field(
        default=80,
        description="Minimum number of offers in a cell to use Z-score gating.",
    )
    small_sample_keep_ratio: float = Field(
        default=0.1,
        description="Ratio of top cheapest offers to keep when sample size is too small.",
    )

    weight_price: float = Field(
        default=0.4,
        description="Weight for normalized price score.",
    )
    weight_rating: float = Field(
        default=0.4,
        description="Weight for normalized rating score.",
    )
    weight_reviews: float = Field(
        default=0.2,
        description="Weight for normalized review count score.",
    )
