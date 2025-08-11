from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.sites.base import BaseSiteService
from src.utils.net_rule_bus import NetRuleBus
from src.sites.xiaohongshu.models import SearchResultItem, SearchAuthor


class XiaohongshuSearchService(BaseSiteService):
    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self.bus = NetRuleBus()
        self._q = None
        self._items: List[SearchResultItem] = []

    async def attach(self, page: Page) -> None:
        self.page = page
        self._unbind = await self.bus.bind(page)
        # 调整正则以匹配搜索接口（示例）
        self._q = self.bus.subscribe(r".*/search.*", kind="response")

    async def search(self, keyword: str, *, max_batches: int = 5, delay_ms: int = 500) -> List[SearchResultItem]:
        if not self.page or not self._q:
            raise RuntimeError("Service not attached")
        self._items = []

        # 触发搜索（示例：在搜索框输入并提交）
        try:
            await self._trigger_search(keyword)
        except Exception:
            pass

        batches = 0
        while batches < max_batches:
            try:
                rv = await asyncio.wait_for(self._q.get(), timeout=5.0)
            except asyncio.TimeoutError:
                break
            data = rv.data()
            await self._parse_search_payload(data)
            batches += 1
            await asyncio.sleep(max(0.05, float(delay_ms) / 1000.0))
            try:
                await self._load_more_results()
            except Exception:
                break
        return list(self._items)

    async def _trigger_search(self, keyword: str) -> None:
        # 站点具体实现：输入关键词并提交
        pass

    async def _load_more_results(self) -> None:
        # 站点具体实现：点击“更多”或滚动以加载更多
        pass

    async def _parse_search_payload(self, payload: Dict[str, Any]) -> None:
        try:
            items = payload.get("data", {}).get("items", [])
            for e in items:
                note = e.get("note_card") or {}
                user = note.get("user", {})
                self._items.append(
                    SearchResultItem(
                        id=str(e.get("id") or note.get("id")),
                        title=str(note.get("title", "")),
                        author=SearchAuthor(
                            user_id=str(user.get("user_id")),
                            username=user.get("nickname"),
                            avatar=user.get("avatar"),
                        ),
                        tags=[t.get("name") for t in note.get("tag_list", [])],
                        url="",  # 可由 note_link 构造
                        snippet=None,
                        timestamp=__import__("datetime").datetime.now().isoformat(),
                    )
                )
        except Exception:
            pass 