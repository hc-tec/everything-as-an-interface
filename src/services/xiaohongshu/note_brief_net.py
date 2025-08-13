from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.base import NoteService, NoteCollectArgs
from src.services.xiaohongshu.collections.note_net_collection import (
    NoteNetCollectionConfig,
    NoteNetCollectionState,
    run_network_collection,
    record_response,
)
from src.utils.net_rule_bus import NetRuleBus, MergedEvent
from src.utils.net_rules import ResponseView
from src.services.xiaohongshu.models import AuthorInfo, NoteStatistics, NoteBriefItem
from src.utils.scrolling import DefaultScrollStrategy, SelectorScrollStrategy, PagerClickStrategy, ScrollStrategy


class XiaohongshuNoteBriefNetService(NoteService[NoteBriefItem]):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = NoteNetCollectionConfig()
        self._bus: Optional[NetRuleBus] = None
        self._merged_q: Optional[asyncio.Queue] = None
        self._subs_meta: Dict[int, tuple[str, str]] = {}
        self._consumer: Optional[asyncio.Task] = None

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NoteNetCollectionState[NoteBriefItem](page=page, event=asyncio.Event())

        # Bind NetRuleBus and subscribe to note responses (multi-pattern ready)
        self._bus = NetRuleBus()
        self._unbind = await self._bus.bind(page)
        self._merged_q, self._subs_meta = self._bus.subscribe_many([
            (r".*/note/collect/page/*", "response"),
            # Add more patterns if needed: (r".*/another_endpoint", "response")
        ])
        # Start background consumer
        self._consumer = asyncio.create_task(self._consume_loop())

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
        if self._consumer:
            try:
                self._consumer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._consumer
            except Exception:
                pass
            self._consumer = None
        await super().detach()

    def set_stop_decider(self, decider) -> None:
        if self.state:
            self.state.stop_decider = decider

    def configure(self, cfg: NoteNetCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: NoteCollectArgs) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        async def on_scroll() -> None:
            try:
                strat: ScrollStrategy
                pause = self._service_config.scroll_pause_ms or self.cfg.scroll_pause_ms
                # Prefer ServiceConfig if specified
                if self._service_config.scroll_mode == "selector" and self._service_config.scroll_selector:
                    strat = SelectorScrollStrategy(self._service_config.scroll_selector, pause_ms=pause)
                elif self._service_config.scroll_mode == "pager" and self._service_config.pager_selector:
                    strat = PagerClickStrategy(self._service_config.pager_selector, wait_ms=pause)
                else:
                    extra = (args.extra_config or {})
                    if extra.get("scroll_selector"):
                        strat = SelectorScrollStrategy(extra["scroll_selector"], pause_ms=pause)
                    elif extra.get("pager_selector"):
                        strat = PagerClickStrategy(extra["pager_selector"], wait_ms=pause)
                    else:
                        strat = DefaultScrollStrategy(pause_ms=pause)
                await strat.scroll(self.page)
            except Exception:
                pass

        items = await run_network_collection(
            self.state,
            self.cfg,
            extra_config=args.extra_config or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
        )
        return items

    async def _consume_loop(self) -> None:
        if not self._merged_q:
            return
        while True:
            try:
                evt: MergedEvent = await self._merged_q.get()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

            if not isinstance(evt.view, ResponseView):
                continue

            try:
                data = evt.view.data()
            except Exception:
                data = None

            if not data or not isinstance(data, dict) or data.get("code") != 0:
                continue

            # Delegate can observe raw response first
            if self._delegate and self.state:
                try:
                    await self._delegate.on_response(evt.view, self.state)
                except Exception:
                    pass

            # Whether to record into state.raw_responses/last_response
            should_record = True
            if self._delegate:
                try:
                    should_record = bool(self._delegate.should_record_response(data, evt.view))
                except Exception:
                    should_record = True
            if should_record and self.state:
                record_response(self.state, data, evt.view)

            # Let delegate parse items first; if returns None, fallback to default
            parsed: Optional[List[NoteBriefItem]] = None
            if self._delegate:
                try:
                    parsed = await self._delegate.parse_items(data)
                except Exception:
                    parsed = None

            if parsed is None:
                # Default parser
                items_payload = data.get("data", {}).get("notes", [])
                parsed = await self._parse_items_default(items_payload)

            # Post-process via delegate and append to state
            if parsed and self.state:
                try:
                    if self._delegate:
                        parsed = await self._delegate.on_items_collected(parsed, self.state)
                except Exception:
                    pass
                try:
                    self.state.items.extend(parsed)
                except Exception:
                    pass
                if self.state.event:
                    try:
                        self.state.event.set()
                    except Exception:
                        pass

    async def _parse_items_default(self, resp_items: List[Dict[str, Any]]) -> List[NoteBriefItem]:
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
