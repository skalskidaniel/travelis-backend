import asyncio
import json
import logging
import random

from pywebpush import webpush, WebPushException

from core.models.user import PushSubscription

logger = logging.getLogger(__name__)

NOTIFICATION_TEMPLATES = [
    {
        "title": "Nowe oferty są dostępne!",
        "body": "Znaleźliśmy nowe oferty turystyczne odpowiadające Twoim preferencjom. Sprawdź aplikację!",
    },
    {
        "title": "Mamy dla Ciebie nowe okazje!",
        "body": "Zaktualizowaliśmy Twoje dopasowania. Zobacz najtańsze wycieczki już teraz!",
    },
    {
        "title": "Pojawiły się nowe okazje wakacyjne!",
        "body": "Zobacz najnowsze oferty dopasowane do Twoich kryteriów zanim znikną!",
    },
]


class NotificationsService:
    """Handles generating and sending Web Push notifications to users."""

    def __init__(
        self, vapid_private_key: str | None, vapid_public_key: str | None
    ) -> None:
        self.private_key = vapid_private_key
        self.public_key = vapid_public_key

    async def send_notification(
        self, subscription: PushSubscription, title: str, body: str
    ) -> None:
        """Sign and send a Web Push notification asynchronously using a thread pool."""
        if not self.private_key or not self.public_key:
            logger.warning("VAPID keys are not configured. Skipping push notification.")
            return

        payload = {
            "title": title,
            "body": body,
        }

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.keys.p256dh,
                "auth": subscription.keys.auth,
            },
        }

        def _send():
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": "mailto:admin@wakacje-travelis.pl"},
            )

        try:
            await asyncio.to_thread(_send)
            logger.info(
                f"Successfully sent push notification to endpoint: {subscription.endpoint}"
            )
        except WebPushException as exc:
            logger.error(f"Failed to send Web Push notification: {exc}")

    async def send_random_notification(self, subscription: PushSubscription) -> None:
        """Select a random template from NOTIFICATION_TEMPLATES and send it."""
        template = random.choice(NOTIFICATION_TEMPLATES)
        await self.send_notification(
            subscription=subscription,
            title=template["title"],
            body=template["body"],
        )
