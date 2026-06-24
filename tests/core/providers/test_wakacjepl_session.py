"""Unit tests for core.providers.wakacjepl.session.warm_up_session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.providers.wakacjepl.session import warm_up_session, _TRUSTED_COOKIE_NAMES


def _make_http_client() -> httpx.AsyncClient:
    """Return a real AsyncClient so we can inspect its cookie jar."""
    return httpx.AsyncClient()


def _mock_curl_session(cookies: dict[str, str], raise_exc: Exception | None = None):
    """Build a context-manager mock for curl_cffi.requests.AsyncSession."""
    mock_session = MagicMock()
    mock_session.cookies.get_dict.return_value = cookies

    if raise_exc:
        mock_session.get = AsyncMock(side_effect=raise_exc)
    else:
        mock_session.get = AsyncMock(return_value=None)

    # Support `async with AsyncSession(...) as session`
    mock_cls = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_cls.return_value = mock_cm

    return mock_cls


@pytest.mark.asyncio
async def test_warm_up_success_injects_cookies():
    """When curl_cffi returns trusted cookies they are injected into the httpx client."""
    cookies = {
        "unleash-session-id": "12345",
        "unleash-toggles": "APP_C.b!S_TAB.a",
        "unleash-context": "%7B%22sessionId%22%3A%2212345%22%7D",
        "WPvw": "1280",  # non-trusted cookie — should NOT be injected
    }
    mock_cls = _mock_curl_session(cookies)
    client = _make_http_client()

    with patch("core.providers.wakacjepl.session.AsyncSession", mock_cls):
        result = await warm_up_session(client)

    assert result is True

    # All trusted cookies must be set on the httpx client
    for name in _TRUSTED_COOKIE_NAMES:
        assert client.cookies.get(name) == cookies[name], (
            f"Expected cookie {name!r} to be injected"
        )

    # Non-trusted cookies must NOT be set
    assert client.cookies.get("WPvw") is None


@pytest.mark.asyncio
async def test_warm_up_no_session_id_returns_false():
    """If the response carries no unleash-session-id cookie, return False."""
    cookies = {"WPvw": "1280"}  # no unleash-session-id
    mock_cls = _mock_curl_session(cookies)
    client = _make_http_client()

    with patch("core.providers.wakacjepl.session.AsyncSession", mock_cls):
        result = await warm_up_session(client)

    assert result is False
    # Nothing should have been injected
    for name in _TRUSTED_COOKIE_NAMES:
        assert client.cookies.get(name) is None


@pytest.mark.asyncio
async def test_warm_up_network_error_returns_false():
    """If curl_cffi raises a network exception, return False without crashing."""
    mock_cls = _mock_curl_session({}, raise_exc=OSError("connection refused"))
    client = _make_http_client()

    with patch("core.providers.wakacjepl.session.AsyncSession", mock_cls):
        result = await warm_up_session(client)

    assert result is False
    for name in _TRUSTED_COOKIE_NAMES:
        assert client.cookies.get(name) is None


@pytest.mark.asyncio
async def test_warm_up_import_error_returns_false():
    """If curl_cffi is not installed (AsyncSession is None), return False gracefully."""
    client = _make_http_client()

    with patch("core.providers.wakacjepl.session.AsyncSession", None):
        result = await warm_up_session(client)

    assert result is False
    for name in _TRUSTED_COOKIE_NAMES:
        assert client.cookies.get(name) is None
