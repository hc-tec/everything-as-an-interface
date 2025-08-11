from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.sites.base import BaseSiteService
from src.utils.net_rule_bus import NetRuleBus
from src.sites.xiaohongshu.models import CommentItem, CommentAuthor


class XiaohongshuCommentService(BaseSiteService):
    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self.bus = NetRuleBus()
        self._q = None
        self._items: List[CommentItem] = []

    async def attach(self, page: Page) -> None:
        self.page = page
        self._unbind = await self.bus.bind(page)
        # 调整正则以匹配评论接口路径（示例）
        self._q = self.bus.subscribe(r".*/note/comments.*", kind="response")

    async def collect_for_note(self, note_id: str, *, max_pages: int = 5, delay_ms: int = 500) -> List[CommentItem]:
        if not self.page or not self._q:
            raise RuntimeError("Service not attached")
        self._items = []

        # 触发评论加载（示例：点击评论按钮或构造接口请求）
        try:
            await self._open_note_and_show_comments(note_id)
        except Exception:
            pass

        pages = 0
        while pages < max_pages:
            try:
                rv = await asyncio.wait_for(self._q.get(), timeout=5.0)
            except asyncio.TimeoutError:
                break
            data = rv.data()
            await self._parse_comments_payload(note_id, data)
            pages += 1
            await asyncio.sleep(max(0.05, float(delay_ms) / 1000.0))
            # 可在此执行“下一页”动作（点击更多、修改偏移等）
            try:
                await self._load_next_comments_page()
            except Exception:
                break
        return list(self._items)

    async def _open_note_and_show_comments(self, note_id: str) -> None:
        # 站点具体实现：打开详情页并点击评论区域
        # 占位：用户可通过外部传入 goto_first 替代
        pass

    async def _load_next_comments_page(self) -> None:
        # 站点具体实现：点击“更多评论”或调整 offset 参数
        pass

    async def _parse_comments_payload(self, note_id: str, payload: Dict[str, Any]) -> None:
        # 参考站点数据结构进行解析，这里做一个结构化示例
        try:
            items = payload.get("data", {}).get("comments", [])
            for c in items:
                author = c.get("user_info", {})
                self._items.append(
                    CommentItem(
                        id=str(c.get("id")),
                        note_id=note_id,
                        author=CommentAuthor(
                            user_id=str(author.get("user_id")),
                            username=author.get("nickname"),
                            avatar=author.get("avatar"),
                        ),
                        content=c.get("content", ""),
                        like_num=int(c.get("like_count", 0)),
                        created_at=str(c.get("time", "")),
                    )
                )
        except Exception:
            pass 