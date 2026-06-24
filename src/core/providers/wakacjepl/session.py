"""Warm up a trusted Wakacje.pl HTTP session using Chrome TLS impersonation.

Wakacje.pl's ``checkOfferAvailability`` endpoint performs TLS fingerprint
verification (JA3/JA4) on the initial HTML page request and internally marks
sessions initiated by plain HTTP clients (httpx) as untrusted bots.  All
subsequent availability API calls under such sessions return ``success: false``
regardless of the offer hash.
"""

from __future__ import annotations

import httpx
from aws_lambda_powertools import Logger

try:
    from curl_cffi.requests import AsyncSession
except ImportError:  # pragma: no cover
    AsyncSession = None  # type: ignore[assignment,misc]

logger = Logger(child=True)

WARMUP_URL = "https://www.wakacje.pl/wczasy/"
_TRUSTED_COOKIE_NAMES = frozenset(
    {"unleash-session-id", "unleash-toggles", "unleash-context"}
)


async def warm_up_session(http_client: httpx.AsyncClient) -> bool:
    """GET the Wakacje.pl homepage with Chrome TLS impersonation.

    Injects the resulting trusted cookies into ``http_client`` so that
    subsequent ``checkOfferAvailability`` calls via plain httpx succeed.

    Args:
        http_client: The shared ``httpx.AsyncClient`` used by ``WakacjePlProvider``.

    Returns:
        ``True`` if a trusted session was established (``unleash-session-id``
        cookie received and injected), ``False`` otherwise.  The job should
        continue even on ``False`` — individual offers will fail gracefully.
    """
    if AsyncSession is None:
        logger.error(
            "curl_cffi is not installed — cannot warm up Wakacje.pl session. "
            "Add 'curl-cffi' to project dependencies."
        )
        return False

    try:
        async with AsyncSession(impersonate="chrome120") as session:
            await session.get(WARMUP_URL, timeout=15)
            cookies: dict[str, str] = session.cookies.get_dict()
    except Exception as exc:
        logger.warning("curl_cffi warm-up request failed: %s", exc)
        return False

    session_id = cookies.get("unleash-session-id")
    if not session_id:
        logger.warning(
            "curl_cffi warm-up completed but no unleash-session-id cookie was received"
        )
        return False

    for name, value in cookies.items():
        if name in _TRUSTED_COOKIE_NAMES:
            http_client.cookies.set(name, value, domain=".wakacje.pl")

    logger.info(
        "Wakacje.pl session warm-up successful (unleash-session-id=%s)", session_id
    )
    return True
