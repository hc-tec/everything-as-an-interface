from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.base import BaseSiteService
from src.utils.net_rule_bus import NetRuleBus
from src.services.xiaohongshu.models import CommentItem, CommentAuthor
from src.services.xiaohongshu.collections.note_net_collection import FeedCollectionState
from src.utils.net_rules import ResponseView
from src.services.paged_collector import PagedCollector


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

    def _default_parser(self, note_id: str):
        async def _parse(payload: Dict[str, Any]) -> List[CommentItem]:
            items: List[CommentItem] = []
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
            return items
        return _parse

    async def collect_for_note(self, note_id: str, *, max_pages: Optional[int] = None, delay_ms: Optional[int] = None, timeout_sec: Optional[float] = None) -> List[CommentItem]:
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

        # Delegate hooks for PagedCollector
        async def _on_resp(rv: ResponseView, state: FeedCollectionState[CommentItem]) -> None:
            if self._delegate:
                try:
                    await self._delegate.on_response(rv, state)
                except Exception:
                    pass

        async def _on_items(batch: List[CommentItem], state: FeedCollectionState[CommentItem]) -> List[CommentItem]:
            if self._delegate:
                try:
                    processed = await self._delegate.on_items_collected(batch, state)
                    return processed
                except Exception:
                    pass
            return batch

        # If delegate provides a custom parser, wrap it
        async def _parser(payload: Dict[str, Any]) -> List[CommentItem]:
            if self._delegate:
                try:
                    ret = await self._delegate.parse_comment_items(payload)
                    if ret is not None:
                        return ret
                except Exception:
                    pass
            return await self._default_parser(note_id)(payload)

        cfg_timeout = timeout_sec if timeout_sec is not None else self._service_config.response_timeout_sec
        cfg_delay = delay_ms if delay_ms is not None else self._service_config.delay_ms
        cfg_pages = max_pages if max_pages is not None else self._service_config.max_pages

        collector = PagedCollector[CommentItem](
            page=self.page,
            queue=self._q,
            state=self._state,
            parser=_parser,
            response_timeout_sec=cfg_timeout,
            delay_ms=cfg_delay,
            max_pages=cfg_pages,
            on_response=_on_resp,
            on_items_collected=_on_items,
        )

        # Inherit stop_decider if provided
        if self._stop_decider:
            self._state.stop_decider = self._stop_decider

        results = await collector.run(extra_config={"note_id": note_id})
        self._items = results
        return list(self._items)

    async def _open_note_and_show_comments(self, note_id: str) -> None:
        # 站点具体实现：打开详情页并点击评论区域
        # 占位：用户可通过外部传入 goto_first 替代（未来可扩展到 CollectArgs）
        pass

    async def _load_next_comments_page(self) -> None:
        # 站点具体实现：点击“更多评论”或调整 offset 参数
        pass 