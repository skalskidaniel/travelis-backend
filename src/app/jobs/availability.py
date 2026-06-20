import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from core.container import Container
from core.models.offer import Offer
from core.models.common import ProviderName

logger = logging.getLogger(__name__)


async def run_availability_job(container: Container, context=None) -> dict:
    """Scan active cells, check availability/pricing of available offers in parallel,

    and persist updates to DynamoDB.
    """
    logger.info("Starting daily availability and price check job.")

    cells = await container.cells_repo.scan()
    if not cells:
        logger.info("No active market cells found. Skipping availability check.")
        return {"checked_offers_count": 0, "updated_offers_count": 0}

    available_offers = []
    for cell in cells:
        cell_offers = await container.offers_repo.query_by_cell(cell.cell_id)
        for offer in cell_offers:
            if offer.available:
                available_offers.append(offer)

    if not available_offers:
        logger.info("No available offers found in database to check.")
        return {"checked_offers_count": 0, "updated_offers_count": 0}

    checked_count = 0
    updated_count = 0
    sem = asyncio.Semaphore(15)

    tui = container.tui_provider
    wakacje = container.wakacje_provider

    async def check_single_offer(offer: Offer):
        nonlocal checked_count, updated_count
        async with sem:
            checked_count += 1
            provider = tui if offer.provider == ProviderName.TUI else wakacje
            try:
                is_available = await provider.check_availability(offer)
                changed = False

                if not is_available:
                    offer.available = False
                    offer.updated_at = datetime.now(timezone.utc)
                    changed = True
                    logger.info(
                        f"Offer {offer.offer_id} ({offer.provider}) is no longer available."
                    )
                else:
                    new_price = await provider.check_price(offer)
                    if new_price != offer.price_total:
                        offer.price_total = new_price
                        offer.price_per_day = (
                            Decimal(str(new_price))
                            / offer.duration
                            / (offer.adults + offer.children)
                        ).quantize(Decimal("0.01"))
                        offer.updated_at = datetime.now(timezone.utc)
                        changed = True
                        logger.info(
                            f"Offer {offer.offer_id} ({offer.provider}) price updated to {new_price}."
                        )

                if changed:
                    await container.offers_repo.put(offer)
                    updated_count += 1

            except Exception as e:
                logger.error(
                    f"Error checking availability/price for offer {offer.offer_id} ({offer.provider}): {e}"
                )

    tasks = [check_single_offer(offer) for offer in available_offers]
    await asyncio.gather(*tasks)

    logger.info(
        f"Availability check complete. Checked: {checked_count}, Updated: {updated_count}"
    )
    return {
        "checked_offers_count": checked_count,
        "updated_offers_count": updated_count,
    }
