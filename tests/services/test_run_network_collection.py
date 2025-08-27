import asyncio
import pytest
from types import SimpleNamespace
from src.services.net_collection_loop import NetCollectionState, run_network_collection
from src.services.base_service import ServiceParams
from src.common.plugin import StopDecision

@pytest.mark.asyncio
async def test_run_network_collection_without_browser():
    fake_page = SimpleNamespace()
    state = NetCollectionState(page=fake_page, queue=asyncio.Queue())
    cfg = ServiceParams(max_items=2, max_seconds=10, max_idle_rounds=5, auto_scroll=False)

    # 模拟“解析后 items 增长 + 唤醒队列”
    async def producer():
        await asyncio.sleep(0.01)
        state.items.append({"id": "a"})
        await state.queue.put(1)
        await asyncio.sleep(0.01)
        state.items.append({"id": "b"})
        await state.queue.put(1)

    prod_task = asyncio.create_task(producer())

    items = await run_network_collection(
        state=state,
        cfg=cfg,
        extra_params={},
        goto_first=None,
        on_scroll=None,
    )

    assert [it["id"] for it in items] == ["a", "b"]
    await prod_task