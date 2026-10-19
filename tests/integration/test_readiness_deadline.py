import asyncio

import pytest

from routes import health


async def test_readiness_deadline_does_not_wait_for_driver_cancellation(monkeypatch):
    monkeypatch.setattr(health, "CHECK_TIMEOUT", 0.01)
    release_cleanup = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def blocked_driver():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            # A paused database can block the driver's cancellation/rollback.
            await release_cleanup.wait()
            cleaned_up.set()
            raise

    try:
        result = await asyncio.wait_for(
            health.checked("db", blocked_driver), timeout=0.2
        )
        assert result == ("error", None)
        assert not cleaned_up.is_set()
    finally:
        release_cleanup.set()
        await asyncio.wait_for(cleaned_up.wait(), timeout=1)


async def test_cancelled_request_cancels_its_readiness_operation():
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def operation():
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    check = asyncio.create_task(health.checked("db", operation))
    await started.wait()
    check.cancel()
    with pytest.raises(asyncio.CancelledError):
        await check
    await asyncio.wait_for(cancelled.wait(), timeout=1)
