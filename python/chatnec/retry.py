"""Retry/backoff for outbound platform API calls (rate limits, transient network
errors). Kept dependency-free (no tenacity) since the retry policy here is
deliberately simple: a handful of attempts with exponential backoff, honoring
Retry-After when a platform sends one.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import httpx

logger = logging.getLogger("chatnec")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def send_with_retry(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
) -> httpx.Response:
    """Call `send()`, retrying on 429/5xx responses and transport errors with
    exponential backoff. Returns the last response (or raises the last
    transport error) once attempts are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(attempts):
        is_last = attempt == attempts - 1
        try:
            response = await send()
        except httpx.TransportError as exc:
            last_exc = exc
            if is_last:
                raise
            delay = base_delay * (2**attempt)
            logger.warning("chatnec: transport error (%s), retrying in %.1fs", exc, delay)
            await asyncio.sleep(delay)
            continue

        if response.status_code not in RETRYABLE_STATUS_CODES or is_last:
            return response

        delay = _retry_delay(response, attempt, base_delay)
        logger.warning(
            "chatnec: platform returned %s, retrying in %.1fs (attempt %d/%d)",
            response.status_code,
            delay,
            attempt + 1,
            attempts,
        )
        await asyncio.sleep(delay)

    assert last_exc is not None  # unreachable: loop always returns or raises above
    raise last_exc


def _retry_delay(response: httpx.Response, attempt: int, base_delay: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return base_delay * (2**attempt)
