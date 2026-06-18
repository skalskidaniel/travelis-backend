import json
import pytest
from unittest.mock import MagicMock, patch

from pywebpush import WebPushException

from core.models.user import PushSubscription, PushSubscriptionKeys
from core.services.notifications import (
    NotificationsService,
    NOTIFICATION_TEMPLATES,
    PushSendResult,
)


@pytest.fixture
def mock_subscription():
    return PushSubscription(
        endpoint="https://updates.push.com/send/user123",
        keys=PushSubscriptionKeys(p256dh="test_p256dh", auth="test_auth"),
    )


@pytest.mark.asyncio
async def test_send_notification_skips_when_keys_missing(mock_subscription):
    service = NotificationsService(vapid_private_key=None, vapid_public_key=None)

    with patch("core.services.notifications.webpush") as mock_webpush:
        result = await service.send_notification(mock_subscription, "Title", "Body")
        mock_webpush.assert_not_called()
        assert result is PushSendResult.SKIPPED


@pytest.mark.asyncio
async def test_send_notification_success(mock_subscription):
    service = NotificationsService(
        vapid_private_key="private_key_pem", vapid_public_key="public_key_pem"
    )

    with patch("core.services.notifications.webpush") as mock_webpush:
        result = await service.send_notification(
            mock_subscription, "Nowa Oferta", "Treść powiadomienia"
        )
        mock_webpush.assert_called_once()
        kwargs = mock_webpush.call_args[1]

        assert kwargs["subscription_info"]["endpoint"] == mock_subscription.endpoint
        assert kwargs["subscription_info"]["keys"]["auth"] == "test_auth"

        assert kwargs["vapid_private_key"] == "private_key_pem"
        assert kwargs["vapid_claims"] == {"sub": "mailto:admin@wakacje-travelis.pl"}

        data_json = json.loads(kwargs["data"])
        assert data_json["title"] == "Nowa Oferta"
        assert data_json["body"] == "Treść powiadomienia"
        assert result is PushSendResult.SENT


@pytest.mark.asyncio
async def test_send_notification_expired_subscription(mock_subscription):
    service = NotificationsService(
        vapid_private_key="private_key_pem", vapid_public_key="public_key_pem"
    )
    response = MagicMock(status_code=410)

    with patch(
        "core.services.notifications.webpush",
        side_effect=WebPushException("gone", response=response),
    ):
        result = await service.send_notification(mock_subscription, "Title", "Body")
        assert result is PushSendResult.EXPIRED


@pytest.mark.asyncio
async def test_send_random_notification(mock_subscription):
    service = NotificationsService(
        vapid_private_key="private_key_pem", vapid_public_key="public_key_pem"
    )

    with patch.object(service, "send_notification") as mock_send:
        mock_send.return_value = PushSendResult.SENT
        result = await service.send_random_notification(mock_subscription)
        mock_send.assert_called_once()
        assert result is PushSendResult.SENT

        called_args = mock_send.call_args[1]
        assert called_args["subscription"] == mock_subscription

        any_match = False
        for template in NOTIFICATION_TEMPLATES:
            if (
                called_args["title"] == template["title"]
                and called_args["body"] == template["body"]
            ):
                any_match = True
                break
        assert any_match, f"Unexpected title/body: {called_args}"
