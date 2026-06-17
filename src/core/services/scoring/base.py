from typing import Protocol
from core.models.offer import RawOffer, ScoredOffer


class OfferScorer(Protocol):
    def score(self, offers: list[RawOffer]) -> list[ScoredOffer]:
        """
        Returns a list of offers passing the Stage 1 gate,
        paired with their Stage 2 attractiveness score.
        """
        ...
