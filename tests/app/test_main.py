from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_container
from app.exceptions import MatchSchedulingException, UnknownJobEventException
from app.main import app, handler


@pytest.fixture
def lambda_context():
    context = MagicMock()
    context.function_name = "travelis-dev-lambdalith"
    context.memory_limit_in_mb = 1024
    context.invoked_function_arn = (
        "arn:aws:lambda:eu-central-1:123456789012:function:travelis-dev-lambdalith"
    )
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def healthy_container():
    c = MagicMock()
    c.settings = MagicMock()
    c.settings.environment = "dev"
    c.settings.frontend_url = "https://wakacje-travelis.pl"
    c.settings.users_table = "test-users"
    c.redis_client = AsyncMock()
    c.redis_client.ping = AsyncMock(return_value=True)
    c.users_repo = MagicMock()
    c.users_repo.table = MagicMock()
    c.users_repo.table.meta = MagicMock()
    c.users_repo.table.meta.client = MagicMock()
    c.users_repo.table.meta.client.describe_table = AsyncMock(return_value={})
    return c


def test_cors_headers(healthy_container):
    app.dependency_overrides[get_container] = lambda: healthy_container
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v2/health",
            headers={
                "Origin": "https://wakacje-travelis.pl",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200

        from core.container import container

        if container.settings.environment == "prod":
            assert "access-control-allow-origin" in response.headers
            assert (
                response.headers["access-control-allow-origin"]
                == container.settings.frontend_url
            )
        else:
            assert "access-control-allow-origin" not in response.headers
    finally:
        app.dependency_overrides.clear()


def test_lambda_handler_api_gateway(lambda_context, healthy_container):
    import asyncio

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    event = {
        "version": "2.0",
        "routeKey": "GET /api/v2/health",
        "rawPath": "/api/v2/health",
        "rawQueryString": "",
        "headers": {
            "accept": "*/*",
            "host": "api.wakacje-travelis.pl",
            "x-forwarded-proto": "https",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "domainName": "api.wakacje-travelis.pl",
            "domainPrefix": "api",
            "http": {
                "method": "GET",
                "path": "/api/v2/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent",
            },
            "requestId": "request-id",
            "routeKey": "GET /api/v2/health",
            "stage": "$default",
            "time": "12/Mar/2020:19:03:58 +0000",
            "timeEpoch": 1583348638385,
        },
        "isBase64Encoded": False,
    }

    app.dependency_overrides[get_container] = lambda: healthy_container
    try:
        response = handler(event, lambda_context)
    finally:
        app.dependency_overrides.clear()

    assert response["statusCode"] == 200
    assert "body" in response


def test_lambda_handler_cognito_post_confirmation(lambda_context):
    event = {
        "version": "1",
        "region": "eu-central-1",
        "userPoolId": "eu-central-1_xxxxxxxxx",
        "userName": "test-user-id",
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "request": {
            "userAttributes": {
                "sub": "test-user-id",
                "email_verified": "true",
                "email": "test@example.com",
            }
        },
        "response": {},
    }

    with (
        patch("app.user.controller.get_or_create_user") as mock_get_or_create,
        patch("app.main.container") as mock_container,
    ):
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()
        response = handler(event, lambda_context)
        assert response == event
        mock_get_or_create.assert_called_once_with("test-user-id", mock_container)


def test_lambda_handler_cognito_post_confirmation_federated(lambda_context):
    event = {
        "version": "1",
        "region": "eu-central-1",
        "userPoolId": "eu-central-1_xxxxxxxxx",
        "userName": "Google_113110676533136880527",
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "request": {
            "userAttributes": {
                "sub": "83845802-8051-7070-75d9-2912768752bd",
                "email_verified": "true",
                "email": "test@example.com",
            }
        },
        "response": {},
    }

    with (
        patch("app.user.controller.get_or_create_user") as mock_get_or_create,
        patch("app.main.container") as mock_container,
    ):
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()
        response = handler(event, lambda_context)
        assert response == event
        mock_get_or_create.assert_called_once_with("83845802-8051-7070-75d9-2912768752bd", mock_container)


def test_lambda_handler_scheduler_match_user(lambda_context):
    event = {"type": "match_user", "user_id": "user-123"}

    with patch("app.main.container") as mock_container:
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()
        mock_container.matching_service.match_user_offers = AsyncMock(return_value=True)

        response = handler(event, lambda_context)

        assert response["status"] == "success"
        assert response["feed_changed"] is True
        mock_container.matching_service.match_user_offers.assert_called_once_with(
            "user-123"
        )


def test_lambda_handler_scheduler_match_user_missing_id(lambda_context):
    event = {"type": "match_user"}

    with patch("app.main.container") as mock_container:
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()

        with pytest.raises(
            MatchSchedulingException, match="Missing user_id for match_user event"
        ):
            handler(event, lambda_context)


def test_lambda_handler_unhandled_event(lambda_context):
    event = {"type": "unknown_event_type"}

    with patch("app.main.container") as mock_container:
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()

        with pytest.raises(UnknownJobEventException, match="unknown_event_type"):
            handler(event, lambda_context)


def test_lambda_handler_scrape_offers(lambda_context):
    event = {"type": "scrape_offers"}

    with (
        patch("app.main.container") as mock_container,
        patch("app.main.run_scrape_job") as mock_run_scrape,
    ):
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()
        mock_run_scrape.return_value = {"scraped_cells": ["cell-1"]}

        response = handler(event, lambda_context)

        assert response["status"] == "success"
        assert "completed" in response["message"]
        assert response["results"]["scraped_cells"] == ["cell-1"]
        mock_run_scrape.assert_called_once()


def test_lambda_handler_check_availability(lambda_context):
    event = {"type": "check_availability"}

    with (
        patch("app.main.container") as mock_container,
        patch("app.main.run_availability_job") as mock_run_availability,
    ):
        mock_container.exit_stack = MagicMock()
        mock_container.initialize = AsyncMock()
        mock_run_availability.return_value = {"checked_offers_count": 5}

        response = handler(event, lambda_context)

        assert response["status"] == "success"
        assert "completed" in response["message"]
        assert response["results"]["checked_offers_count"] == 5
        mock_run_availability.assert_called_once()
