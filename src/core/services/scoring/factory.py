from core.services.scoring.base import OfferScorer
from core.services.scoring.config import StatisticalScorerConfig
from core.services.scoring.statistical import StatisticalOfferScorer


def get_scorer(
    version: str = "statistical", config: StatisticalScorerConfig | None = None
) -> OfferScorer:
    """
    Factory function to instantiate the requested OfferScorer.

    Args:
        version: The scoring algorithm version to use (default: "statistical").
        config: Optional configuration model for the scorer.

    Returns:
        An instance of an OfferScorer.

    Raises:
        ValueError: If an unknown version is requested.
    """
    if version == "statistical":
        return StatisticalOfferScorer(config=config)

    raise ValueError(f"Unknown scoring version: {version}")
