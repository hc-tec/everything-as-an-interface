import asyncio
import pytest
from types import SimpleNamespace
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_collection_loop import NetCollectionState
from src.utils.net_rule_bus import MergedEvent
from src.utils.net_rules import ResponseView
from src.services.net_service import NetServiceDelegate

@pytest.mark.asyncio
async def test_net_consume_helper_consumes_and_parses():
    # 1) 构造 state 与 helper（无需真实 Page）
    fake_page = SimpleNamespace()
    state = NetCollectionState(page=fake_page, queue=asyncio.Queue())
    delegate = NetServiceDelegate()
    helper = NetConsumeHelper(state=state, delegate=delegate)

    # 2) 构造“合并队列”，直接塞给 helper（绕过 bind）
    merged_q = asyncio.Queue()
    helper._merged_q = merged_q  # 直接注入测试队列

    # 3) 定义默认解析函数与回调
    async def default_parse_items(payload):
        return [{"id": it["id"], "title": it["title"]} for it in payload.get("items", [])]

    seen = []
    async def on_items_collected(items, consume_count, extra, st):
        seen.extend(items)
        return items
    delegate.on_items_collected = on_items_collected

    # 4) 启动消费循环
    await helper.start(default_parse_items=default_parse_items)

    # 5) 投递三个事件（使用最小 ResponseView 替身）
    class DummyResp: url = "https://api.example.com/list"
    for i in range(3):
        payload = {"items": [{"id": f"n{i}", "title": f"T{i}"}]}
        rv = ResponseView(DummyResp(), payload)
        await merged_q.put(MergedEvent(sub_id=i+1, kind="response", view=rv))

    # 等待消费
    await asyncio.sleep(0.1)

    # 6) 断言 helper 已写入 state.items，并调用回调
    assert len(state.items) == 3
    assert len(seen) == 3

    # 7) 清理
    await helper.stop()