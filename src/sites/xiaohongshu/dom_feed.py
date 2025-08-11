from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, ElementHandle

from src.sites.base import FeedService, FeedCollectArgs
from src.utils.dom_collection import (
    DomCollectionConfig,
    DomCollectionState,
    run_dom_collection,
)
from src.plugins.xiaohongshu import FavoriteItem, AuthorInfo, NoteStatistics


class XiaohongshuDomFeedService(FeedService[FavoriteItem]):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = DomCollectionConfig()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = DomCollectionState[FavoriteItem](page=page)

    def set_stop_decider(self, decider) -> None:
        # DOM 模式暂不支持 decider（可扩展为基于 items 的自定义检查）
        pass

    def configure(self, cfg: DomCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: FeedCollectArgs) -> List[FavoriteItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        async def goto_first() -> None:
            if args.goto_first:
                await args.goto_first()

        async def extract_once(page: Page, acc: List[FavoriteItem]) -> int:
            added = 0
            items = await page.query_selector_all(".tab-content-item:nth-child(2) .note-item")
            for item in items:
                parsed = await self._parse_note_from_dom(item)
                if parsed:
                    acc.append(parsed)
                    added += 1
            return added

        results = await run_dom_collection(
            self.state,
            self.cfg,
            goto_first=goto_first,
            extract_once=extract_once,
        )
        return results

    # 下面的解析逻辑与插件一致，必要时可重用或抽到 parser 模块
    async def _parse_note_from_dom(self, item: ElementHandle) -> Optional[FavoriteItem]:
        try:
            cover_ele = await item.query_selector(".title")
            if cover_ele:
                await cover_ele.click()
                await asyncio.sleep(0.4)

            def get_text(ele, default=""):
                return ele.text_content() if ele else default

            def get_attr(ele, name, default=""):
                return ele.get_attribute(name) if ele else default

            item_id = "unknown"
            item_anchor = await item.query_selector("a")
            if item_anchor:
                link = await item_anchor.get_attribute("href")
                if link:
                    item_id = link.split("/")[-1]

            note_container = await item.query_selector(".note-detail-mask")
            title_ele = await note_container.query_selector("#detail-title") if note_container else None
            title_val = await get_text(title_ele) if title_ele else ""

            avatar_ele = await note_container.query_selector(".avatar-item") if note_container else None
            avatar_val = await get_attr(avatar_ele, "src") if avatar_ele else ""

            username_ele = await note_container.query_selector(".username") if note_container else None
            username_val = await get_text(username_ele) if username_ele else ""

            tag_ele_list = await note_container.query_selector_all(".note-text > .tag") if note_container else []
            tags: List[str] = []
            for tag_ele in tag_ele_list or []:
                txt = await tag_ele.text_content()
                if txt:
                    tags.append(txt)

            date_ele = await note_container.query_selector(".date") if note_container else None
            date_val = ""
            ip_zh_val = ""
            if date_ele:
                date_ip_val = await date_ele.text_content()
                if date_ip_val:
                    parts = date_ip_val.split()
                    if len(parts) == 1:
                        date_val = parts[0]
                    elif len(parts) >= 2:
                        if "创建" in parts[0] or "编辑" in parts[0]:
                            date_val = parts[1]
                        else:
                            date_val = parts[0]
                            ip_zh_val = parts[1]

            comment_ele = await note_container.query_selector(".total") if note_container else None
            comment_val = await get_text(comment_ele) if comment_ele else "0"

            engage = await note_container.query_selector(".engage-bar-style") if note_container else None
            like_val = collect_val = chat_val = "0"
            if engage:
                like_ele = await engage.query_selector(".like-wrapper > .count")
                collect_ele = await engage.query_selector(".collect-wrapper > .count")
                chat_ele = await engage.query_selector(".chat-wrapper > .count")
                like_val = await get_text(like_ele) if like_ele else "0"
                collect_val = await get_text(collect_ele) if collect_ele else "0"
                chat_val = await get_text(chat_ele) if chat_ele else "0"

            # 关闭详情
            close_ele = await item.query_selector(".close-circle")
            if close_ele:
                try:
                    await close_ele.click(timeout=2000)
                except Exception:
                    pass

            return FavoriteItem(
                id=item_id,
                title=title_val,
                author_info=AuthorInfo(username=username_val, avatar=avatar_val, user_id=None),
                tags=tags,
                date=date_val,
                ip_zh=ip_zh_val,
                comment_num=comment_val,
                statistic=NoteStatistics(like_num=like_val, collect_num=collect_val, chat_num=chat_val),
                images=None,
                video=None,
                timestamp=__import__("datetime").datetime.now().isoformat(),
            )
        except Exception:
            return None 