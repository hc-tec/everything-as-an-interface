from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from playwright.async_api import Page

from src.config import get_logger
from src.services.models import AuthorInfo, NoteStatistics
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.xiaohongshu.models import NoteBriefItem

logger = get_logger(__name__)

class XiaohongshuNoteCollectionBriefNetService(NetService[NoteBriefItem]):
    """
    小红书收藏夹笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[NoteBriefItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/sns/web/v1/board/note/*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper)

        await super().attach(page)

    async def invoke(self, extra_params: Dict[str, Any]) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(
            self.page,
            service_params=self._service_params,
            pause_ms=pause,
            extra=extra_params
        )

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
                                   state: Any) -> List[NoteBriefItem]:
        items_payload = payload.get("data").get("notes", [])
        results: List[NoteBriefItem] = []
        for note_item in items_payload or []:
            try:
                id = note_item["note_id"]
                title = note_item.get("display_title")
                xsec_token = note_item.get("xsec_token")
                user = note_item.get("user", {})
                author_info = AuthorInfo(
                    username=user.get("nick_name"),
                    avatar=user.get("avatar"),
                    user_id=user.get("user_id"),
                    xsec_token=user.get("xsec_token")
                )
                interact = note_item.get("interact_info", {})
                statistic = NoteStatistics(
                    like_num=str(interact.get("liked_count", 0)),
                    collect_num=str(interact.get("collected_count", 0)),
                    chat_num=str(interact.get("comment_count", 0)),
                )
                cover_image = note_item.get("cover", {}).get("url_default")
                results.append(
                    NoteBriefItem(
                        id=id,
                        xsec_token=xsec_token,
                        title=title,
                        author_info=author_info,
                        statistic=statistic,
                        cover_image=cover_image,
                        raw_data=self._inject_raw_data(note_item),
                    )
                )
            except Exception as e:
                logger.error(f"note parse error：{str(e)}")
        return results
