from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.models.cell import MarketCell
    from core.models.offer import Offer, Provider
    from core.models.raw_offer import RawOffer


@runtime_checkable
class OfferProvider(Protocol):
    """Port for a travel-offer source adapter (wakacje.pl, tui.pl, …).

    Adapters own all provider-specific HTTP, field mapping, and auth. They return
    ``RawOffer`` rows for ingest; nothing past that boundary should depend on
    provider response shapes.
    """

    @property
    def provider(self) -> Provider:
        """Which provider this adapter implements."""
        ...

    async def search(self, cell: MarketCell) -> list[RawOffer]:
        """Fetch offers for a global market cell.

        Called once per active cell per scrape run. Departure airport and duration
        filters are intentionally broad at scrape time; user-specific filtering
        happens later in matching.
        """
        ...

    async def check_availability(self, offer: Offer) -> bool:
        """Return whether a persisted offer is still bookable.

        Uses provider metadata captured at ingest (``metadata.wakacje`` or
        ``metadata.tui``) together with canonical offer fields.
        """
        ...
        
    async def check_price(self, offer: Offer) -> Decimal:
        """Return an updated offer price."""
        ...
