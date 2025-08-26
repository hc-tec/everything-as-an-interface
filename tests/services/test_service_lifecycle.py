import asyncio
from typing import Callable, Any, Dict

import pytest
from playwright.async_api import Page, Response

from src.services.base_service import ServiceParams
from src.services.xiaohongshu.common import NoteCollectArgs
from src.services.xiaohongshu.note_brief_net import XiaohongshuNoteBriefNetService
from src.utils.net_rules import ResponseView


class FakeResponse(Response):
    """极简 Response stub，仅实现测试用到的属性/方法"""
    def __init__(self, url: str, status: int, json_body: Any):
        self._url = url
        self._status = status
        self._json_body = json_body

    # playwright.Response API 兼容字段
    @property
    def url(self) -> str: return self._url

    def status(self) -> int: return self._status  # type: ignore[override]

    async def json(self) -> Any: return self._json_body
    async def text(self) -> str: return str(self._json_body)
    async def body(self) -> bytes: return str(self._json_body).encode()

    # 其余属性按需补充
    @property
    def headers(self) -> Dict[str, str]: return {}

def fake_response_view(url: str, payload: Any, status: int = 200) -> ResponseView:
    return ResponseView(FakeResponse(url, status, payload), payload)

class FakePage(Page):
    """最小实现: 只支持 on('response') & evaluate / goto 等被用到的方法"""
    def __init__(self):
        self._response_handlers = []

    # playwright Page API -----
    def on(self, event: str, handler: Callable):
        if event == "response":
            self._response_handlers.append(handler)

    async def goto(self, url: str, **kwargs):     # noqa: D401
        return None                               # 不做任何事

    async def evaluate(self, script: str, arg=None):
        return None

    # 测试辅助 ------------
    async def emit_response(self, resp: Response):
        for h in self._response_handlers:
            await h(resp)


@pytest.mark.skip
@pytest.mark.asyncio
async def test_full_lifecycle():
    page = FakePage()
    svc = XiaohongshuNoteBriefNetService()

    await svc.attach(page)          # 绑定 fake page
    svc.set_params(ServiceParams(max_items=10))

    # 注入 3 个假网络包
    for i in range(3):
        payload = {"data": {"notes": [{"note_id": str(i)}]}}
        view = fake_response_view("https://edith.xiaohongshu.com/api/...", payload)
        await page.emit_response(view._original)  # FakePage -> handler -> parse

    # give internal queue consumer chance to run
    await asyncio.sleep(0.1)

    args = NoteCollectArgs()  # 使用默认收集参数
    items = await svc.collect(args=args)
    assert len(items) >= 3

    await svc.detach()