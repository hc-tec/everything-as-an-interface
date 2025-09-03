
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.collection_common import StopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.bilibili.models import VideoSubtitleList, VideoSubtitleItem


class VideoAiSubtitleNetService(NetService[VideoSubtitleList]):
    """
    Bilibili AI字幕抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[VideoSubtitleList](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/ai_subtitle/prod.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def detach(self) -> None:
        self.state = None
        await self._net_helper.stop()
        self._net_helper = None
        await super().detach()

    async def invoke(self, extra_params: Dict[str, Any]) -> List[VideoSubtitleList]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(extra_params)

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params,
                                                 pause_ms=pause, extra=extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            delegate=self.loop_delegate,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[VideoSubtitleList]:
        lang = payload["lang"]
        type = payload["type"]
        subtitle_data = payload["body"]
        subtitles = []
        for item in subtitle_data:
            subtitles.append(VideoSubtitleItem(
                content=item["content"],
                from_=item["from"],
                to=item["to"],
                location=item["location"],
                sid=item["sid"],
            ))
        return [
            VideoSubtitleList(
                subtitles=subtitles,
                lang=lang,
                type=type,
                raw_data=self._inject_raw_data(payload)
            )
        ]
