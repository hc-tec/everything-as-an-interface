import asyncio
import pytest
from types import SimpleNamespace

from src.services.net_service import NetServiceDelegate
from src.services.xiaohongshu.note_brief_net import XiaohongshuNoteBriefNetService
from src.services.base_service import ServiceConfig
from src.services.net_collection import NetCollectionState
from src.services.net_consume_helpers import NetConsumeHelper
from src.utils.net_rule_bus import MergedEvent
from src.utils.net_rules import ResponseView


@pytest.mark.asyncio
async def test_note_brief_service_collect_minimal(monkeypatch):
    svc = XiaohongshuNoteBriefNetService()
    fake_page = SimpleNamespace()  # 无浏览器

    # 1) 干掉 attach 里的 bind/start（不触发 page.on / .off）
    async def fake_bind(self, page, patterns):
        # 给 helper 准备一个可控 merged 队列（即便本例不用它）
        self._merged_q = asyncio.Queue()
    async def fake_start(self, *, default_parse_items, payload_ok=None):
        return
    monkeypatch.setattr(NetConsumeHelper, "bind", fake_bind, raising=False)
    monkeypatch.setattr(NetConsumeHelper, "start", fake_start, raising=False)

    # 2) 正常走 attach 建立基础结构（但不会真的绑定）
    await svc.attach(fake_page)

    # 3) 注入我们自己的 state（队列 + items），跳过网络监听，直接驱动循环
    state = NetCollectionState(page=fake_page, queue=asyncio.Queue())
    svc.state = state
    svc.configure(ServiceConfig(max_items=2, auto_scroll=False, max_seconds=5))

    # 4) 后台喂“解析后的”items，并唤醒队列，驱动 run_network_collection 退出
    async def feed():
        await asyncio.sleep(0.01)
        state.items.append({"id": "1", "title": "A"})
        await state.queue.put(1)
        await asyncio.sleep(0.01)
        state.items.append({"id": "2", "title": "B"})
        await state.queue.put(1)
    task = asyncio.create_task(feed())

    # 5) collect 会调用 run_network_collection，直到 max_items=2
    args = SimpleNamespace(goto_first=None, extra_config={})
    items = await svc.collect(args=args)

    assert [it["id"] for it in items] == ["1", "2"]
    await task



@pytest.mark.asyncio
async def test_helper_parsing_chain_without_browser():
    fake_page = SimpleNamespace()
    state = NetCollectionState(page=fake_page, queue=asyncio.Queue())
    delegate = NetServiceDelegate()
    helper = NetConsumeHelper(state=state, delegate=delegate)

    # 准备合并队列（不需要 bind）
    merged_q = asyncio.Queue()
    helper._merged_q = merged_q

    async def default_parse_items(payload):
        return [{"id": it["id"], "title": it["title"]} for it in payload.get("items", [])]

    seen = []
    async def on_items_collected(items, consume_count, extra, st):
        seen.extend(items); return items
    delegate.on_items_collected = on_items_collected

    await helper.start(default_parse_items=default_parse_items)

    class DummyResp: url = "https://api.example.com/list"
    for i in range(2):
        payload = {"items": [{"id": f"n{i}", "title": f"T{i}"}]}
        rv = ResponseView(DummyResp(), payload)
        await merged_q.put(MergedEvent(sub_id=i+1, kind="response", view=rv))

    await asyncio.sleep(0.05)  # 等消费
    assert [it["id"] for it in state.items] == ["n0", "n1"]
    assert [it["id"] for it in seen] == ["n0", "n1"]
    await helper.stop()

