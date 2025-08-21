
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.xiaohongshu.common import NoteService, NoteCollectArgs
from src.services.collection_common import NetStopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection import (
    NetCollectionState,
    run_network_collection,
)
from src.services.xiaohongshu.models import NoteDetailsItem
from src.services.xiaohongshu.parsers import quick_extract_initial_state, parse_details_from_network


class XiaohongshuNoteExplorePageNetService(NoteService[NoteDetailsItem]):
    """
    小红书笔记详情抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取笔记数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[NoteDetailsItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/explore/.*xsec_token.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def collect(self, args: NoteCollectArgs) -> List[NoteDetailsItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(args.extra_config)

        pause = self._service_config.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_config=self._service_config,
                                                 pause_ms=pause, extra=args.extra_config)

        items = await run_network_collection(
            self.state,
            self._service_config,
            extra_config=args.extra_config or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
            on_tick_start=args.on_tick_start
        )
        return items

    async def _parse_items_wrapper(self, payload: Dict[str, Any]) -> List[NoteDetailsItem]:
        payload = payload.get("data")
        if payload is None:
            return []
        js_content = quick_extract_initial_state(payload)
        if js_content:
            data = await self.page.evaluate(f"window.__INITIAL_STATE__ = {js_content}")
            noteDetailMap = data["note"]["noteDetailMap"]
            note = None
            for key, value in noteDetailMap.items():
                if "note" in value:
                    note = value["note"]
                    break
            return parse_details_from_network(note)
        return []

