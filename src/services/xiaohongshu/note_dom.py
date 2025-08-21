from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import Locator, Page

from src.services.scroll_helper import ScrollHelper
from src.services.xiaohongshu.common import NoteService, NoteCollectArgs
from src.services.xiaohongshu.collections.note_dom_collection import (
    NoteDomCollectionConfig,
    NoteDomCollectionState,
    run_dom_collection,
)
from src.services.xiaohongshu.models import NoteDetailsItem
from src.services.xiaohongshu.parsers import parse_details_from_dom


class XiaohongshuNoteDomService(NoteService[NoteDetailsItem]):
    """
    小红书笔记详情抓取服务 - 通过DOM解析实现
    """
    def __init__(self) -> None:
        super().__init__()
        self.cfg = NoteDomCollectionConfig()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NoteDomCollectionState[NoteDetailsItem](page=page, queue=asyncio.Queue())

        # Delegate hook
        if self.delegate.on_attach:
            try:
                await self.delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        # Delegate hook
        if self.delegate.on_detach:
            try:
                await self.delegate.on_detach()
            except Exception:
                pass
        await super().detach()

    def configure(self, cfg: NoteDomCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: NoteCollectArgs) -> List[NoteDetailsItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_config.scroll_pause_ms or self.cfg.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_config=self._service_config, pause_ms=pause, extra=args.extra_config)

        items = await run_dom_collection(
            self.state,
            self.cfg,
            on_scroll=on_scroll,
        )
        return items

    async def parse_from_dom(self, item: Locator) -> Optional[NoteDetailsItem]:
        try:
            return await parse_details_from_dom(item)
        except Exception:
            logging.exception("parse note dom failed")
            return None