import sys
import os
import asyncio

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

from core.container import container
from core.models.offer import Offer


async def main():
    await container.initialize()
    try:
        repo = container.offers_repo
        provider = container.wakacje_provider

        offers: List[Offer] = await repo.scan()

        for o in offers:
            if o.provider == "wakacje_pl":
                available: bool = await provider.check_availability(o)
                print(f"Offer {o.referral_url} {available=}", end="\n\n")
    finally:
        await container.cleanup()


if __name__ == "__main__":
    asyncio.run(main())