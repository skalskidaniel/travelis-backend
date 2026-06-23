import asyncio
import json
from aws_lambda_powertools import Logger
from datetime import datetime, time, timezone

from core.container import Container
from core.models.cell import MarketCell
from core.models.offer import Offer
from core.services.ingest import (
    ingest_raw_offers,
    merge_existing_and_new_offer,
    compute_offer_id,
)
from core.services.scoring import get_scorer, StatisticalScorerConfig

logger = Logger(child=True)


def is_timeout_approaching(context, threshold_ms: int = 15000) -> bool:
    """Check if the Lambda function has less than threshold_ms left to execute."""
    if context is None:
        return False
    if not hasattr(context, "get_remaining_time_in_millis"):
        return False
    return context.get_remaining_time_in_millis() < threshold_ms


async def search_with_retry(
    search_fn, cell: MarketCell, provider_name: str, max_retries: int = 3
) -> list:
    """Execute provider search with exponential backoff retries."""
    for attempt in range(1, max_retries + 1):
        try:
            return await search_fn(cell)
        except Exception as e:
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {provider_name} on cell {cell.cell_id}: {e}"
            )
            if attempt == max_retries:
                raise
            # Exponential backoff sleep (shorter base for tests compatibility)
            await asyncio.sleep(0.2 * (2**attempt))
    return []


async def run_scrape_job(container: Container, context=None, payload=None) -> dict:
    """Scrapes active cells, norm/scores, batch persists with availability-by-absence,

    and runs bulk re-match. If Lambda timeout is approaching, it invokes self-continuation.
    """
    payload = payload or {}

    # 1. Resolve cell list to scrape
    remaining_cells_ids = payload.get("remaining_cells")
    if remaining_cells_ids:
        logger.info(
            f"Resuming scrape coordinator job for {len(remaining_cells_ids)} cells."
        )
        cells = await container.cells_repo.get_batch(remaining_cells_ids)
    else:
        logger.info("Starting fresh scrape coordinator job.")
        cells = await container.cells_repo.scan()

    if not cells:
        logger.info("No active market cells to scrape.")
        return {"scraped_cells": [], "matched_users": [], "continued": False}

    # 2. Build worker pool
    queue = asyncio.Queue()
    for cell in cells:
        await queue.put(cell)

    scraped_cell_ids = []
    timeout_triggered = False

    tui = container.tui_provider
    wakacje = container.wakacje_provider

    async def worker():
        nonlocal timeout_triggered
        while not queue.empty():
            if is_timeout_approaching(context):
                logger.warning("Lambda timeout approaching! Worker stopping.")
                timeout_triggered = True
                break

            cell = await queue.get()
            try:
                tui_task = search_with_retry(tui.search, cell, "TUI")
                wakacje_task = search_with_retry(wakacje.search, cell, "WakacjePl")

                tui_raw, wakacje_raw = await asyncio.gather(
                    tui_task, wakacje_task, return_exceptions=True
                )

                raw_offers = []
                if isinstance(tui_raw, list):
                    raw_offers.extend(tui_raw)
                else:
                    logger.error(
                        f"TUI search failed for cell {cell.cell_id}: {tui_raw}"
                    )

                if isinstance(wakacje_raw, list):
                    raw_offers.extend(wakacje_raw)
                else:
                    logger.error(
                        f"WakacjePl search failed for cell {cell.cell_id}: {wakacje_raw}"
                    )

                if not raw_offers:
                    logger.info(f"No raw offers scraped for cell {cell.cell_id}")
                    continue

                collapsed_raw = ingest_raw_offers(raw_offers)
                if not collapsed_raw:
                    continue

                scorer = get_scorer(
                    config=StatisticalScorerConfig(
                        z_threshold=container.settings.scoring.attractiveness_z_threshold
                    )
                )
                scored_offers = await asyncio.to_thread(scorer.score, collapsed_raw)
                if not scored_offers:
                    continue

                now = datetime.now(timezone.utc)
                new_offers_map = {}
                for scored in scored_offers:
                    try:
                        oid = compute_offer_id(scored)
                        expected_ttl = int(
                            datetime.combine(
                                scored.departure_date,
                                time.min,
                                tzinfo=timezone.utc,
                            ).timestamp()
                        )
                        offer = Offer(
                            **scored.model_dump(),
                            cell_id=cell.cell_id,
                            offer_id=oid,
                            # share_url is overridden automatically by Offer's validation logic to build the canonical URL
                            share_url="https://wakacje-travelis.pl/offer/dummy/dummy",
                            scraped_at=now,
                            updated_at=now,
                            ttl=expected_ttl,
                        )
                        new_offers_map[oid] = offer
                    except Exception as e:
                        logger.warning(
                            f"Skipping invalid offer from provider {scored.provider} "
                            f"(external_id={scored.external_offer_id}, hotel={scored.hotel_name}) "
                            f"in cell {cell.cell_id} due to validation error: {e}"
                        )

                if not new_offers_map:
                    logger.error(
                        f"All {len(scored_offers)} scored offers failed validation for cell {cell.cell_id}; "
                        "skipping persistence to avoid marking existing offers unavailable."
                    )
                    continue

                existing_offers = await container.offers_repo.query_by_cell(
                    cell.cell_id
                )
                existing_map = {o.offer_id: o for o in existing_offers}

                offers_to_save = []

                for oid, new_offer in new_offers_map.items():
                    if oid in existing_map:
                        merged = merge_existing_and_new_offer(
                            existing_map[oid], new_offer
                        )
                        offers_to_save.append(merged)
                    else:
                        offers_to_save.append(new_offer)

                # Availability-by-absence logic
                for oid, existing_offer in existing_map.items():
                    if oid not in new_offers_map and existing_offer.available:
                        existing_offer.available = False
                        existing_offer.updated_at = now
                        offers_to_save.append(existing_offer)

                await container.offers_repo.put_batch(offers_to_save)
                await container.cells_repo.update_last_scraped([cell.cell_id], now)

                scraped_cell_ids.append(cell.cell_id)

            except Exception as e:
                logger.error(f"Unhandled error scraping cell {cell.cell_id}: {e}")
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(min(10, len(cells)))]
    await asyncio.gather(*workers)

    # 3. Handle timeout approaching self-triggering continuation
    continued = False
    if timeout_triggered and not queue.empty():
        unscraped_ids = []
        while not queue.empty():
            cell = queue.get_nowait()
            unscraped_ids.append(cell.cell_id)
            queue.task_done()

        if unscraped_ids:
            if container.settings.lambda_function_arn and container.lambda_client:
                logger.info(
                    f"Triggering asynchronous scraper continuation for {len(unscraped_ids)} remaining cells."
                )
                continuation_payload = {
                    "type": "scrape_offers",
                    "remaining_cells": unscraped_ids,
                }
                await container.lambda_client.invoke(
                    FunctionName=container.settings.lambda_function_arn,
                    InvocationType="Event",
                    Payload=json.dumps(continuation_payload),
                )
                continued = True
            else:
                logger.warning(
                    "LAMBDA_FUNCTION_ARN or lambda_client is missing. Cannot trigger continuation."
                )

    # 4. Trigger bulk matching on successfully scraped cells
    matched_users = []
    if scraped_cell_ids:
        logger.info(f"Running bulk user matching for {len(scraped_cell_ids)} cells.")
        matched_users = await container.matching_service.bulk_match_users(
            scraped_cell_ids
        )

    return {
        "scraped_cells": scraped_cell_ids,
        "matched_users": matched_users,
        "continued": continued,
    }
