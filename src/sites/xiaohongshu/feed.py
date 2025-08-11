from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.sites.base import FeedService, FeedCollectArgs
from src.utils.feed_collection import (
    FeedCollectionConfig,
    FeedCollectionState,
    run_network_collection,
    record_response,
)
from src.utils.net_rules import net_rule_match, bind_network_rules, ResponseView, RuleContext
from src.plugins.xiaohongshu import FavoriteItem, AuthorInfo, NoteStatistics


class XiaohongshuFeedService(FeedService[FavoriteItem]):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = FeedCollectionConfig()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = FeedCollectionState[FavoriteItem](page=page, event=asyncio.Event())

        # Bind network rules locally to service
        # We attach handlers onto self (service) so they can update state directly
        self._unbind = await bind_network_rules(page, self)

    def set_stop_decider(self, decider) -> None:
        if self.state:
            self.state.stop_decider = decider

    def configure(self, cfg: FeedCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: FeedCollectArgs) -> List[FavoriteItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        async def goto_first() -> None:
            if args.goto_first:
                await args.goto_first()

        items = await run_network_collection(
            self.state,
            self.cfg,
            extra_config=args.extra_config or {},
            goto_first=goto_first,
        )
        return items

    # ---------- Network rule handlers ----------
    @net_rule_match(r".*/feed", kind="response")
    async def _capture_feed(self, rule: RuleContext, response: ResponseView):
        try:
            data = response.data()
            if not data or data.get("code") != 0:
                return
            record_response(self.state, data, response)
            await self._parse_items(data.get("data", {}).get("items", []))
        except Exception:
            pass

    async def _parse_items(self, resp_items: List[Dict[str, Any]]) -> None:
        if not self.state:
            return
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
                self.state.items.append(
                    FavoriteItem(
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
        if self.state.event:
            try:
                self.state.event.set()
            except Exception:
                pass 