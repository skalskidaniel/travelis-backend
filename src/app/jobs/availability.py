import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from aws_lambda_powertools import Logger

from core.container import Container
from core.models.cell import MarketCell
from core.models.offer import Offer, mark_offer_unavailable
from core.models.common import ProviderName
from core.providers.base import OfferProvider

logger = Logger(child=True)


async def run_availability_job(container: Container, context=None) -> dict:
    """Scan active cells, check availability/pricing of available offers in parallel,

    and persist updates to DynamoDB.
    """
    logger.info("Starting daily availability and price check job.")

    cells: list[MarketCell] = await container.cells_repo.scan()
    if not cells:
        logger.info("No active market cells found. Skipping availability check.")
        return {
            "checked_offers_count": 0,
            "updated_offers_count": 0,
            "unavailable_offers_count": 0,
            "remain_available_count": 0,
        }

    active_cell_ids = {cell.cell_id for cell in cells}
    all_offers = await container.offers_repo.scan()
    available_offers: list[Offer] = [
        offer
        for offer in all_offers
        if offer.available and offer.cell_id in active_cell_ids
    ]

    if not available_offers:
        logger.info("No available offers found in database to check.")
        return {
            "checked_offers_count": 0,
            "updated_offers_count": 0,
            "unavailable_offers_count": 0,
            "remain_available_count": 0,
        }

    logger.debug(
        "Scanning database: found %d available offers across %d cells to verify",
        len(available_offers),
        len(cells),
    )

    checked_count = 0
    updated_count = 0
    sem = asyncio.Semaphore(15)
    unavailable_cell_ids = set()
    offers_to_update = []

    tui: OfferProvider = container.tui_provider
    wakacje: OfferProvider = container.wakacje_provider

    async def check_single_offer(offer: Offer):
        nonlocal checked_count, updated_count
        async with sem:
            checked_count += 1
            provider: OfferProvider = (
                tui if offer.provider == ProviderName.TUI else wakacje
            )
            logger.debug(
                "Checking availability for offer %s (provider=%s, cell_id=%s)",
                offer.offer_id,
                offer.provider,
                offer.cell_id,
            )
            try:
                is_available = await provider.check_availability(offer)

                if not is_available:
                    now = datetime.now(timezone.utc)
                    offers_to_update.append(mark_offer_unavailable(offer, now=now))
                    unavailable_cell_ids.add(offer.cell_id)
                    logger.info(
                        f"Offer {offer.offer_id} ({offer.provider}) is no longer available. "
                        "Soft-deleted with 14-day TTL."
                    )
                else:
                    logger.debug(
                        "Offer %s is still available. Verifying price (current: %s)...",
                        offer.offer_id,
                        offer.price_total,
                    )
                    new_price = await provider.check_price(offer)
                    if new_price != offer.price_total:
                        offer.price_total = new_price
                        offer.price_per_person = (
                            Decimal(str(new_price)) / (offer.adults + offer.children)
                        ).quantize(Decimal("0.01"))
                        offer.price_per_day = (
                            Decimal(str(new_price))
                            / offer.duration
                            / (offer.adults + offer.children)
                        ).quantize(Decimal("0.01"))
                        offer.updated_at = datetime.now(timezone.utc)
                        offers_to_update.append(offer)
                        updated_count += 1
                        logger.info(
                            f"Offer {offer.offer_id} ({offer.provider}) price updated to {new_price}."
                        )
                    else:
                        logger.debug(
                            "Offer %s price is unchanged (%s)",
                            offer.offer_id,
                            offer.price_total,
                        )

            except Exception as e:
                logger.error(
                    f"Error checking availability/price for offer {offer.offer_id} ({offer.provider}): {e}"
                )

    tasks = [check_single_offer(offer) for offer in available_offers]
    await asyncio.gather(*tasks)

    unavailable_count = sum(1 for o in offers_to_update if not o.available)

    if offers_to_update:
        await container.offers_repo.put_batch(offers_to_update)
        logger.info(
            f"Batch updated {len(offers_to_update)} offers "
            f"({unavailable_count} soft-deleted, {updated_count} price updates)."
        )

    if unavailable_cell_ids:
        logger.info(
            f"Triggering bulk user matching for {len(unavailable_cell_ids)} cell(s) "
            "affected by availability soft-deletes."
        )
        await container.matching_service.bulk_match_users(list(unavailable_cell_ids))

    remain_available_count = checked_count - unavailable_count
    logger.info(
        f"Availability check complete. Checked: {checked_count}, "
        f"Remain Available: {remain_available_count}, Unavailable: {unavailable_count}, "
        f"Price Updates: {updated_count}"
    )
    return {
        "checked_offers_count": checked_count,
        "updated_offers_count": updated_count,
        "unavailable_offers_count": unavailable_count,
        "remain_available_count": remain_available_count,
    }
