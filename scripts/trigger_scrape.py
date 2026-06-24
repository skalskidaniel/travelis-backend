#!/usr/bin/env python3
import asyncio
import sys
import argparse
import os
from typing import List


def load_env():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    os.environ.setdefault(key, val)


load_env()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from aws_lambda_powertools import Logger  # noqa: E402
from core.container import container  # noqa: E402
from app.jobs.coordinator import run_scrape_job  # noqa: E402

logger = Logger(service="travelis-backend")


async def list_cells():
    """Scan and list all active market cells in DynamoDB."""
    logger.info("Initializing connection to DynamoDB...")
    await container.initialize()
    try:
        cells = await container.cells_repo.scan()
        if not cells:
            logger.warning("No active market cells found in the database.")
            return

        logger.info(f"Found {len(cells)} active market cell(s):")
        print("-" * 115)
        print(
            f"{'Cell ID':<18} | {'Country':<7} | {'Month':<8} | {'Stars':<5} | {'Board':<15} | {'Adults':<6} | {'Children':<8} | {'Last Scraped':<25}"
        )
        print("-" * 115)
        for cell in cells:
            last_scraped = (
                cell.last_scraped_at.isoformat() if cell.last_scraped_at else "Never"
            )
            board_name = (
                cell.board.name if hasattr(cell.board, "name") else str(cell.board)
            )
            print(
                f"{cell.cell_id:<18} | {cell.country:<7} | {cell.month:<8} | {cell.min_stars:<5} | {board_name:<15} | {cell.adults:<6} | {cell.children:<8} | {last_scraped:<25}"
            )
        print("-" * 115)
    except Exception as e:
        logger.exception(f"Error fetching cells: {e}")
    finally:
        await container.cleanup()


async def trigger_scrape(cell_ids: List[str] | None):
    """Trigger the scrape coordinator job."""
    logger.info("Initializing container services...")
    await container.initialize()
    try:
        payload = {}
        if cell_ids:
            payload["remaining_cells"] = cell_ids
            logger.info(f"Triggering scrape job for specific cells: {cell_ids}")
        else:
            logger.info("Triggering fresh scrape job for all active cells...")

        results = await run_scrape_job(container, payload=payload)

        logger.info("Scrape Job Completed successfully.")
        print("\n=== Scrape Job Completed ===")
        print("Status: Success")
        print(f"Scraped Cells: {results.get('scraped_cells', [])}")
        print(f"Matched Users: {results.get('matched_users', [])}")
        print(f"Continued (asynchronously): {results.get('continued', False)}")

    except Exception as e:
        logger.exception(f"Error running scrape job: {e}")
    finally:
        await container.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Trigger TraveLis local scraping job.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run",
        action="store_true",
        help="Run the scraping job. Use --cells to target specific cells.",
    )
    group.add_argument(
        "--list-cells",
        action="store_true",
        help="List all active market cells from the database.",
    )
    parser.add_argument(
        "--cells",
        nargs="+",
        help="Optional space-separated list of cell IDs to scrape (only used with --run).",
    )

    args = parser.parse_args()

    if args.list_cells:
        asyncio.run(list_cells())
    elif args.run:
        asyncio.run(trigger_scrape(args.cells))


if __name__ == "__main__":
    main()
