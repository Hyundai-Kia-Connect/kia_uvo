"""Render work is shared and must not return a stale capture after a recapture."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from test_region_operation_serialization import coordinator


def render_coordinator():
    result = coordinator()
    result._svm_dewarp = {}
    result._cache_svm_details(
        "synthetic",
        SimpleNamespace(
            captured_at=None, image_bytes=b"synthetic", image_sizes=(5, 1, 1, 1, 1, 1)
        ),
    )
    return result


async def test_concurrent_views_share_one_render():
    result = render_coordinator()
    entered = asyncio.Event()
    finish = asyncio.Event()

    async def render(*args):
        entered.set()
        await finish.wait()
        return {"front": b"first"}

    result.hass.async_add_executor_job = AsyncMock(side_effect=render)
    tasks = [
        asyncio.create_task(result.async_get_svm_views("synthetic")) for _ in range(5)
    ]
    await entered.wait()
    finish.set()
    assert await asyncio.gather(*tasks) == [{"front": b"first"}] * 5
    result.hass.async_add_executor_job.assert_awaited_once()


async def test_recapture_during_render_returns_new_image():
    result = render_coordinator()
    entered = asyncio.Event()
    finish = asyncio.Event()
    count = 0

    async def render(*args):
        nonlocal count
        count += 1
        if count == 1:
            entered.set()
            await finish.wait()
            return {"front": b"old"}
        return {"front": b"new"}

    result.hass.async_add_executor_job = AsyncMock(side_effect=render)
    task = asyncio.create_task(result.async_get_svm_views("synthetic"))
    await entered.wait()
    result._cache_svm_details(
        "synthetic",
        SimpleNamespace(
            captured_at=None, image_bytes=b"new", image_sizes=(5, 1, 1, 1, 1, 1)
        ),
    )
    finish.set()
    assert await task == {"front": b"new"}
    assert count == 2
    assert result.get_svm_render_diagnostics() == [
        {"state": "complete", "view_count": 1}
    ]
    assert "synthetic" not in repr(result.get_svm_render_diagnostics())


async def test_empty_renderer_output_is_diagnosable():
    result = render_coordinator()
    result.hass.async_add_executor_job = AsyncMock(return_value={})
    with pytest.raises(HomeAssistantError, match="could not be decoded"):
        await result.async_get_svm_views("synthetic")
    assert result.get_svm_render_diagnostics() == [
        {
            "state": "failed",
            "view_count": 0,
            "failure_category": "invalid_image_or_layout",
        }
    ]


async def test_renderer_exception_does_not_expose_private_data():
    result = render_coordinator()
    result.hass.async_add_executor_job = AsyncMock(
        side_effect=ValueError("SYNTHETIC_SECRET")
    )
    with pytest.raises(HomeAssistantError, match="could not be rendered") as error:
        await result.async_get_svm_views("synthetic")
    assert "SYNTHETIC_SECRET" not in str(error.value)
    assert "SYNTHETIC_SECRET" not in repr(result.get_svm_render_diagnostics())


async def test_cancelled_view_waits_for_renderer_before_next_view_starts():
    result = render_coordinator()
    entered = asyncio.Event()
    finish = asyncio.Event()
    calls = 0

    async def render(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await finish.wait()
        return {"front": b"first"}

    result.hass.async_add_executor_job = AsyncMock(side_effect=render)
    first = asyncio.create_task(result.async_get_svm_views("synthetic"))
    await entered.wait()
    first.cancel()
    second = asyncio.create_task(result.async_get_svm_views("synthetic"))
    await asyncio.sleep(0)
    assert calls == 1
    assert not first.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await second == {"front": b"first"}
