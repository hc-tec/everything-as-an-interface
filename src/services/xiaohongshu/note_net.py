from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.base import NoteService, NoteCollectArgs
from src.services.xiaohongshu.collections.note_net_collection import (
    NoteNetCollectionConfig,
    NoteNetCollectionState,
    run_network_collection,
)
from src.services.helpers import ScrollHelper, NetConsumeHelper
from src.utils.net_rule_bus import NetRuleBus, MergedEvent
from src.utils.net_rules import ResponseView
from src.services.xiaohongshu.models import AuthorInfo, NoteStatistics, NoteDetailsItem
from src.utils.scrolling import DefaultScrollStrategy, SelectorScrollStrategy, PagerClickStrategy, ScrollStrategy


class XiaohongshuNoteNetService(NoteService[NoteDetailsItem]):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = NoteNetCollectionConfig()
        self._net_helper: Optional[NetConsumeHelper[NoteDetailsItem]] = None

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NoteNetCollectionState[NoteDetailsItem](page=page, event=asyncio.Event())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self._delegate)
        await self._net_helper.bind(page, [
            (r".*/feed", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_default_wrapper)

        # Delegate hook
        if self._delegate:
            try:
                await self._delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        # Delegate hook (before unbind)
        if self._delegate:
            try:
                await self._delegate.on_detach()
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

    async def collect(self, args: NoteCollectArgs) -> List[NoteDetailsItem]:
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

    async def _parse_items_default_wrapper(self, payload: Dict[str, Any]) -> List[NoteDetailsItem]:
        items_payload = payload.get("items", [])
        return await self._parse_items_default(items_payload)

    async def _parse_items_default(self, resp_items: List[Dict[str, Any]]) -> List[NoteDetailsItem]:
        results: List[NoteDetailsItem] = []
        for note_item in resp_items or []:
            try:
                id = note_item["id"]
                note_card = note_item["note_card"]
                title = note_card.get("title")
                user = note_card.get("user", {})
                author_info = AuthorInfo(
                    username=user.get("nickname"),
                    avatar=user.get("avatar"),
                    user_id=user.get("user_id"),
                )
                tag_list = [tag.get("name") for tag in note_card.get("tag_list", [])]
                date = note_card.get("time")
                ip_zh = note_card.get("ip_location")
                interact = note_card.get("interact_info", {})
                comment_num = str(interact.get("comment_count", 0))
                statistic = NoteStatistics(
                    like_num=str(interact.get("liked_count", 0)),
                    collect_num=str(interact.get("collected_count", 0)),
                    chat_num=str(interact.get("comment_count", 0)),
                )
                images = [image.get("url_default") for image in note_card.get("image_list", [])]
                results.append(
                    NoteDetailsItem(
                        id=id,
                        title=title,
                        author_info=author_info,
                        tags=tag_list,
                        date=date,
                        ip_zh=ip_zh,
                        comment_num=comment_num,
                        statistic=statistic,
                        images=images,
                        video=None,
                        timestamp=__import__("datetime").datetime.now().isoformat(),
                    )
                )
            except Exception:
                continue
        return results 
