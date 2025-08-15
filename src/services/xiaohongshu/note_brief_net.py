from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.base import NoteService, NoteCollectArgs
from src.services.xiaohongshu.collections.note_net_collection import (
    NoteNetCollectionConfig,
    NoteNetCollectionState,
    run_network_collection,
)
from src.services.helpers import ScrollHelper, NetConsumeHelper
from src.services.xiaohongshu.models import AuthorInfo, NoteStatistics, NoteBriefItem


class XiaohongshuNoteBriefNetService(NoteService[NoteBriefItem]):
    """
    小红书瀑布流笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()
        self.cfg = NoteNetCollectionConfig()
        self._net_helper: Optional[NetConsumeHelper[NoteBriefItem]] = None

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NoteNetCollectionState[NoteBriefItem](page=page, event=asyncio.Event())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/note/collect/page/*", "response"),
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

    def configure(self, cfg: NoteNetCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: NoteCollectArgs) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_config.scroll_pause_ms or self.cfg.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_config=self._service_config, pause_ms=pause, extra=args.extra_config)

        items = await run_network_collection(
            self.state,
            self.cfg,
            extra_config=args.extra_config or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
        )
        return items

    async def _parse_items_wrapper(self, payload: Dict[str, Any]) -> List[NoteBriefItem]:
        items_payload = payload.get("notes", [])
        return await self._parse_items(items_payload)

    async def _parse_items(self, resp_items: List[Dict[str, Any]]) -> List[NoteBriefItem]:
        results: List[NoteBriefItem] = []
        for note_item in resp_items or []:
            try:
                id = note_item["note_id"]
                title = note_item.get("display_title")
                xsec_token = note_item.get("xsec_token")
                user = note_item.get("user", {})
                author_info = AuthorInfo(
                    username=user.get("nickname"),
                    avatar=user.get("avatar"),
                    user_id=user.get("user_id"),
                    xsec_token=user.get("xsec_token")
                )
                interact = note_item.get("interact_info", {})
                statistic = NoteStatistics(
                    like_num=str(interact.get("liked_count", 0)),
                    collect_num=None,
                    chat_num=None
                )
                cover_image = note_item.get("cover").get("url_default")
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
