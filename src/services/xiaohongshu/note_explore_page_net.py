
from __future__ import annotations
from glom import glom
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.base import NoteService, NoteCollectArgs
from src.services.collection_common import NetStopDecider
from src.services.helpers import ScrollHelper, NetConsumeHelper
from src.services.xiaohongshu.collections.note_net_collection import (
    NoteNetCollectionConfig,
    NoteNetCollectionState,
    run_network_collection,
)
from src.services.xiaohongshu.models import AuthorInfo, NoteStatistics, NoteDetailsItem, VideoInfo
from src.utils.file_util import write_file_with_project_root


def quick_extract_initial_state(html_content):
    """
    快速提取HTML文件中的window.__INITIAL_STATE__

    Args:
        html_content (str): HTML文档
    """

    # 正则表达式：匹配包含window.__INITIAL_STATE__的script标签
    pattern = r'<script[^>]*>.*?window\.__INITIAL_STATE__\s*=\s*(.+?)(?=\s*;|\s*</script>|\s*$).*?</script>'

    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)

    if match:
        state_value = match.group(1).strip()
        logging.debug("找到 window.__INITIAL_STATE__:")
        return state_value
    return None

class XiaohongshuNoteExplorePageNetService(NoteService[NoteDetailsItem]):
    """
    小红书笔记详情抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取笔记数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()
        self.cfg = NoteNetCollectionConfig()
        self._net_helper: Optional[NetConsumeHelper[NoteDetailsItem]] = None

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NoteNetCollectionState[NoteDetailsItem](page=page, event=asyncio.Event())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/explore/.*xsec_token.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

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

    def set_stop_decider(self, decider: NetStopDecider) -> None:
        if self.state:
            self.state.stop_decider = decider

    def configure(self, cfg: NoteNetCollectionConfig) -> None:
        self.cfg = cfg

    async def collect(self, args: NoteCollectArgs) -> List[NoteDetailsItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(args.extra_config)

        pause = self._service_config.scroll_pause_ms or self.cfg.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_config=self._service_config,
                                                 pause_ms=pause, extra=args.extra_config)

        items = await run_network_collection(
            self.state,
            self.cfg,
            extra_config=args.extra_config or {},
            goto_first=args.goto_first,
            on_scroll=on_scroll,
            on_tick_start=args.on_tick_start
        )
        return items

    async def _parse_items_wrapper(self, payload: Dict[str, Any]) -> List[NoteDetailsItem]:
        js_content = quick_extract_initial_state(payload)
        if js_content:
            data = await self.page.evaluate(f"window.__INITIAL_STATE__ = {js_content}")
            noteDetailMap = data["note"]["noteDetailMap"]
            note = None
            for key, value in noteDetailMap.items():
                if "note" in value:
                    note = value["note"]
                    break
            return await self._parse_items(note)
        return []

    async def _parse_items(self, note_item: Dict[str, Any]) -> List[NoteDetailsItem]:
        results: List[NoteDetailsItem] = []
        try:
            id = note_item["noteId"]
            title = note_item.get("title")
            desc = note_item.get("desc")
            user = note_item.get("user", {})
            author_info = AuthorInfo(
                username=user.get("nickname"),
                avatar=user.get("avatar"),
                user_id=user.get("userId"),
                xsec_token=user.get("xsecToken"),
            )
            tag_list = [tag.get("name") for tag in note_item.get("tagList", [])]
            date = note_item.get("time")
            ip_zh = note_item.get("ipLocation")
            interact = note_item.get("interactInfo", {})
            comment_num = str(interact.get("commentCount", 0))
            statistic = NoteStatistics(
                like_num=str(interact.get("likedCount", 0)),
                collect_num=str(interact.get("collectedCount", 0)),
                chat_num=str(interact.get("commentCount", 0)),
            )
            images = [image.get("urlDefault").replace("\u002F", "/") for image in note_item.get("imageList", [])]
            video = note_item.get("video", None)
            video_info = None
            if video:
                duration_sec = video.get("capa").get("duration")
                src = glom(video, ("media.stream.h265.0.masterUrl"), default=None)
                if src:
                    src = src.replace("\u002F", "/")
                video_id = video.get("media").get("videoId")
                video_info = VideoInfo(id=video_id, src=src, duration_sec=duration_sec)
            results.append(
                NoteDetailsItem(
                    id=id,
                    title=title,
                    desc=desc,
                    author_info=author_info,
                    tags=tag_list,
                    date=date,
                    ip_zh=ip_zh,
                    comment_num=comment_num,
                    statistic=statistic,
                    images=images,
                    video=video_info,
                    timestamp=__import__("datetime").datetime.now().isoformat(),
                )
            )
        except Exception as e:
            logging.error("note parse error", exc_info=e)
        return results 
