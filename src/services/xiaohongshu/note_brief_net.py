from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.net_collection import (
    NetCollectionState,
    run_network_collection,
)
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.scroll_helper import ScrollHelper
from src.services.xiaohongshu.common import NoteService, NoteCollectArgs
from src.services.xiaohongshu.models import NoteBriefItem
from src.services.xiaohongshu.parsers import parse_brief_from_network


class XiaohongshuNoteBriefNetService(NoteService[NoteBriefItem]):
    """
    小红书瀑布流笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[NoteBriefItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/note/collect/page/*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper)

        await super().attach(page)

    async def collect(self, args: NoteCollectArgs) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params, pause_ms=pause, extra=args.extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=args.extra_params or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[NoteBriefItem]:
        items_payload = payload.get("data").get("notes", [])
        return parse_brief_from_network(items_payload, raw_data=self._inject_raw_data(payload))
