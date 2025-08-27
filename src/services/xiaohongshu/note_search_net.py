from __future__ import annotations

import asyncio
from src.config import get_logger
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.xiaohongshu.models import NoteBriefItem, AuthorInfo, NoteStatistics

logger = get_logger(__name__)

class XiaohongshuNoteSearchNetService(NetService[NoteBriefItem]):
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
            (r".*/search/notes", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper)

        await super().attach(page)

    async def invoke(self, extra_params: Dict[str, Any]) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params, pause_ms=pause, extra=extra_params)

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
                                   state: Any
                                   ) -> List[NoteBriefItem]:
        items_payload = payload.get("data").get("items", [])
        results: List[NoteBriefItem] = []
        for note_item in items_payload or []:
            try:
                if note_item["model_type"] != "note":
                    continue
                id = note_item["id"]
                xsec_token = note_item.get("xsec_token")
                note_card = note_item["note_card"]
                title = note_card.get("display_title")
                user = note_card.get("user", {})
                author_info = AuthorInfo(
                    username=user.get("nickname"),
                    avatar=user.get("avatar"),
                    user_id=user.get("user_id"),
                    xsec_token=user.get("xsec_token")
                )
                interact = note_card.get("interact_info", {})
                statistic = NoteStatistics(
                    like_num=str(interact.get("liked_count", 0)),
                    collect_num=str(interact.get("collected_count", 0)),
                    chat_num=str(interact.get("comment_count", 0))
                )
                cover_image = note_card.get("cover", {}).get("url_default")
                results.append(
                    NoteBriefItem(
                        id=id,
                        xsec_token=xsec_token,
                        title=title,
                        author_info=author_info,
                        statistic=statistic,
                        cover_image=cover_image,
                        raw_data=note_item
                    )
                )
            except Exception as e:
                logger.error(f"解析笔记信息出错：{str(e)}")
        return results
