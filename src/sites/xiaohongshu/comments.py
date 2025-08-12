from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.sites.base import BaseSiteService
from src.utils.net_rule_bus import NetRuleBus
from src.sites.xiaohongshu.models import CommentItem, CommentAuthor
from src.utils.feed_collection import record_response, FeedCollectionState
from src.utils.net_rules import ResponseView


class CommentsServiceDelegate:
    """Optional delegate for customizing comment collection behavior."""

    async def on_attach(self, page: Page) -> None:  # pragma: no cover - default no-op
        return None

    async def on_detach(self) -> None:  # pragma: no cover - default no-op
        return None

    async def on_response(self, response: ResponseView, state: FeedCollectionState[CommentItem]) -> None:  # pragma: no cover - default no-op
        return None

    async def parse_comment_items(self, payload: Dict[str, Any]) -> Optional[List[CommentItem]]:  # pragma: no cover - default None
        return None

    async def on_items_collected(self, items: List[CommentItem], state: FeedCollectionState[CommentItem]) -> List[CommentItem]:  # pragma: no cover - default passthrough
        return items

    async def before_next_page(self, page_index: int) -> None:  # pragma: no cover - default no-op
        return None


class XiaohongshuCommentService(BaseSiteService):
    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self.bus = NetRuleBus()
        self._q: Optional[asyncio.Queue] = None
        self._items: List[CommentItem] = []
        # Shared state borrowed from feed collection primitives for consistency
        self._state: Optional[FeedCollectionState[CommentItem]] = None
        self._delegate: Optional[CommentsServiceDelegate] = None
        self._stop_decider = None

    def set_delegate(self, delegate: Optional[CommentsServiceDelegate]) -> None:  # pragma: no cover - simple setter
        self._delegate = delegate

    def set_stop_decider(self, decider) -> None:  # pragma: no cover - optional support
        """Set a stop decider with the same signature as Feed StopDecider.

        page, all_raw, last_raw, all_items, last_batch, elapsed, extra_config, last_view -> bool
        """
        self._stop_decider = decider

    async def attach(self, page: Page) -> None:
        self.page = page
        self._unbind = await self.bus.bind(page)
        # 订阅评论接口（按需调整正则以适配真实路径）
        self._q = self.bus.subscribe(r".*/note/comments.*", kind="response")
        # 初始化 state
        self._state = FeedCollectionState[CommentItem](page=page, event=asyncio.Event())
        if self._delegate:
            try:
                await self._delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        if self._delegate:
            try:
                await self._delegate.on_detach()
            except Exception:
                pass
        await super().detach()

    async def collect_for_note(self, note_id: str, *, max_pages: int = 5, delay_ms: int = 500, timeout_sec: int = 30) -> List[CommentItem]:
        if not self.page or not self._q or not self._state:
            raise RuntimeError("Service not attached")
        self._items = []
        # 清理 state
        self._state.items.clear()
        self._state.raw_responses.clear()
        self._state.last_raw_response = None
        self._state.last_response_view = None
        try:
            self._state.event.clear()
        except Exception:
            self._state.event = asyncio.Event()

        # 触发首屏评论加载（示例：点击评论按钮或构造接口请求）
        try:
            await self._open_note_and_show_comments(note_id)
        except Exception:
            pass

        start = time.monotonic()
        pages = 0
        last_len = 0
        extra_cfg: Dict[str, Any] = {"note_id": note_id, "max_pages": max_pages}

        while pages < max_pages and (time.monotonic() - start) < timeout_sec:
            try:
                rv: ResponseView = await asyncio.wait_for(self._q.get(), timeout=5.0)
            except asyncio.TimeoutError:
                break

            # Delegate observe response
            if self._delegate and self._state:
                try:
                    await self._delegate.on_response(rv, self._state)
                except Exception:
                    pass

            payload = rv.data()
            if not isinstance(payload, dict):
                continue

            # Record raw payload into state
            if self._state:
                record_response(self._state, payload, rv)

            # Parse comments (delegate first)
            batch: Optional[List[CommentItem]] = None
            if self._delegate:
                try:
                    batch = await self._delegate.parse_comment_items(payload)
                except Exception:
                    batch = None
            if batch is None:
                batch = self._parse_comments_payload(note_id, payload)

            # Post-process & append
            if batch and self._state:
                try:
                    if self._delegate:
                        batch = await self._delegate.on_items_collected(batch, self._state)
                except Exception:
                    pass
                self._items.extend(batch)
                self._state.items.extend(batch)
                if self._state.event:
                    try:
                        self._state.event.set()
                    except Exception:
                        pass

            # Stop-decider check (reusing feed-like signature)
            new_len = len(self._items)
            if self._stop_decider and self._state:
                try:
                    elapsed = time.monotonic() - start
                    new_batch = self._items[last_len:new_len]
                    result = self._stop_decider(
                        self.page,
                        self._state.raw_responses,
                        self._state.last_raw_response,
                        self._items,
                        new_batch,
                        elapsed,
                        extra_cfg,
                        self._state.last_response_view,
                    )
                    should_stop = await result if asyncio.iscoroutine(result) else bool(result)
                    if should_stop:
                        break
                except Exception:
                    pass
            last_len = new_len

            pages += 1
            # Pagination hook
            if self._delegate:
                try:
                    await self._delegate.before_next_page(pages)
                except Exception:
                    pass
            # Load next
            try:
                await self._load_next_comments_page()
            except Exception:
                break
            await asyncio.sleep(max(0.05, float(delay_ms) / 1000.0))

        return list(self._items)

    async def _open_note_and_show_comments(self, note_id: str) -> None:
        # 站点具体实现：打开详情页并点击评论区域
        # 占位：用户可通过外部传入 goto_first 替代（未来可扩展到 CollectArgs）
        pass

    async def _load_next_comments_page(self) -> None:
        # 站点具体实现：点击“更多评论”或调整 offset 参数
        pass

    def _parse_comments_payload(self, note_id: str, payload: Dict[str, Any]) -> List[CommentItem]:
        items: List[CommentItem] = []
        try:
            comments = payload.get("data", {}).get("comments", [])
            for c in comments or []:
                author = c.get("user_info", {})
                items.append(
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
            return []
        return items 