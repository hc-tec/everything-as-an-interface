from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.xiaohongshu.common import NoteService, NoteCollectArgs
from src.services.net_collection import (
    NetCollectionState,
    run_network_collection,
)
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.scroll_helper import ScrollHelper
from src.services.xiaohongshu.models import NoteBriefItem, AuthorInfo, NoteStatistics


class XiaohongshuNoteSearchNetService(NoteService[NoteBriefItem]):
    """
    小红书瀑布流笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()
        self._net_helper: Optional[NetConsumeHelper[NoteBriefItem]] = None

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[NoteBriefItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/search/notes", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper)

        # Delegate hook
        if self.delegate.on_attach:
            try:
                await self.delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        # Delegate hook (before unbind)
        if self.delegate.on_detach:
            try:
                await self.delegate.on_detach()
            except Exception:
                pass
        # Stop consumer
        if self._net_helper:
            try:
                await self._net_helper.stop()
            except Exception:
                pass
        await super().detach()

    def set_stop_decider(self, decider) -> None:
        if self.state:
            self.state.stop_decider = decider

    async def collect(self, args: NoteCollectArgs) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_config.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_config=self._service_config, pause_ms=pause, extra=args.extra_config)

        items = await run_network_collection(
            self.state,
            self._service_config,
            extra_config=args.extra_config or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
        )
        return items

    async def _parse_items_wrapper(self, payload: Dict[str, Any]) -> List[NoteBriefItem]:
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
                    )
                )
            except Exception as e:
                logging.error(f"解析笔记信息出错：{str(e)}")
        return results
