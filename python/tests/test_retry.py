import httpx
import pytest

from chatnec.retry import send_with_retry


@pytest.mark.asyncio
async def test_returns_immediately_on_success():
    calls = 0

    async def send():
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://test"))

    response = await send_with_retry(send, attempts=3, base_delay=0)

    assert response.status_code == 200
    assert calls == 1


@pytest.mark.asyncio
async def test_retries_on_retryable_status_then_succeeds():
    calls = 0

    async def send():
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, request=httpx.Request("POST", "http://test"))
        return httpx.Response(200, request=httpx.Request("POST", "http://test"))

    response = await send_with_retry(send, attempts=3, base_delay=0)

    assert response.status_code == 200
    assert calls == 3


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts():
    calls = 0

    async def send():
        nonlocal calls
        calls += 1
        return httpx.Response(500, request=httpx.Request("POST", "http://test"))

    response = await send_with_retry(send, attempts=2, base_delay=0)

    assert response.status_code == 500
    assert calls == 2


@pytest.mark.asyncio
async def test_does_not_retry_non_retryable_status():
    calls = 0

    async def send():
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=httpx.Request("POST", "http://test"))

    response = await send_with_retry(send, attempts=3, base_delay=0)

    assert response.status_code == 400
    assert calls == 1


@pytest.mark.asyncio
async def test_retries_on_transport_error_then_raises():
    calls = 0

    async def send():
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(httpx.ConnectError):
        await send_with_retry(send, attempts=2, base_delay=0)

    assert calls == 2
