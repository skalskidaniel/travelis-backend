import asyncio
import json
from aws_lambda_powertools import Logger
import random
from enum import Enum

from pywebpush import webpush, WebPushException

from core.models.user import PushSubscription

logger = Logger(child=True)

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

EXPIRED_SUBSCRIPTION_STATUS_CODES = frozenset({404, 410})


class PushSendResult(str, Enum):
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"
    EXPIRED = "expired"


class NotificationsService:
    """Handles generating and sending Web Push notifications to users."""

    def __init__(
        self, vapid_private_key: str | None, vapid_public_key: str | None
    ) -> None:
        self.private_key = vapid_private_key
        self.public_key = vapid_public_key

    async def send_notification(
        self, subscription: PushSubscription, title: str, body: str
    ) -> PushSendResult:
        """Sign and send a Web Push notification asynchronously using a thread pool."""
        if not self.private_key or not self.public_key:
            logger.warning("VAPID keys are not configured. Skipping push notification.")
            return PushSendResult.SKIPPED

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
            return PushSendResult.SENT
        except WebPushException as exc:
            if _is_expired_subscription(exc):
                logger.warning(
                    "Push subscription expired or invalid for endpoint %s: %s",
                    subscription.endpoint,
                    exc,
                )
                return PushSendResult.EXPIRED

            logger.error(f"Failed to send Web Push notification: {exc}")
            return PushSendResult.FAILED

    async def send_random_notification(
        self, subscription: PushSubscription
    ) -> PushSendResult:
        """Select a random template from NOTIFICATION_TEMPLATES and send it."""
        template = random.choice(NOTIFICATION_TEMPLATES)
        return await self.send_notification(
            subscription=subscription,
            title=template["title"],
            body=template["body"],
        )


def _is_expired_subscription(exc: WebPushException) -> bool:
    response = getattr(exc, "response", None)
    if response is None:
        return False
    return response.status_code in EXPIRED_SUBSCRIPTION_STATUS_CODES
