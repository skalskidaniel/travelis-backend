import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from aws_lambda_powertools import Logger

from core.container import Container
from core.models.cell import MarketCell
from core.models.offer import Offer
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
            "deleted_offers_count": 0,
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
            "deleted_offers_count": 0,
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
    deleted_cell_ids = set()
    offers_to_delete = []
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
                    offers_to_delete.append((offer.cell_id, offer.offer_id))
                    deleted_cell_ids.add(offer.cell_id)
                    logger.info(
                        f"Offer {offer.offer_id} ({offer.provider}) is no longer available. Deleted."
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

    if offers_to_delete:
        await container.offers_repo.delete_batch(offers_to_delete)
        logger.info(f"Batch deleted {len(offers_to_delete)} unavailable offers.")

    if offers_to_update:
        await container.offers_repo.put_batch(offers_to_update)
        logger.info(f"Batch updated {len(offers_to_update)} offers with new prices.")

    if deleted_cell_ids:
        logger.info(
            f"Triggering bulk user matching for {len(deleted_cell_ids)} cell(s) affected by availability deletions."
        )
        await container.matching_service.bulk_match_users(list(deleted_cell_ids))

    deleted_count = len(offers_to_delete)
    remain_available_count = checked_count - deleted_count
    logger.info(
        f"Availability check complete. Checked: {checked_count}, "
        f"Remain Available: {remain_available_count}, Deleted: {deleted_count}, "
        f"Price Updates: {updated_count}"
    )
    return {
        "checked_offers_count": checked_count,
        "updated_offers_count": updated_count,
        "deleted_offers_count": deleted_count,
        "remain_available_count": remain_available_count,
    }
