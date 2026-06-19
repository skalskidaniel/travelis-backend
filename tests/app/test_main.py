from app.main import handler


def test_cors_headers(client):
    response = client.get(
        "/api/v2/health",
        headers={
            "Origin": "https://wakacje-travelis.pl",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] in [
        "*",
        "https://wakacje-travelis.pl",
    ]


def test_lambda_handler_api_gateway():
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

    response = handler(event, None)

    assert response["statusCode"] == 200
    assert "body" in response


def test_lambda_handler_unhandled_event():
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

    response = handler(event, None)
    assert response is not None
