
from __future__ import annotations
import asyncio
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.collection_common import StopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.models import AuthorInfo
from src.services.bilibili.models import BiliVideoDetails, VideoStatistic, VideoDimension, AudioUrl, VideoUrl
from src.services.xiaohongshu.parsers import extract_initial_state
from src.config import get_logger

logger = get_logger(__name__)

def extract_initial_state(html_content: str) -> Optional[str]:
    """
    快速提取HTML文件中的window.__INITIAL_STATE__

    Args:
        html_content (str): HTML文档

    Returns:
        Optional[str]: 提取到的状态值，如果未找到则返回None
    """
    pattern = r'<script[^>]*>.*?window\.__INITIAL_STATE__\s*=\s*(.+?)(?=\s*;|\s*</script>|\s*$).*?</script>'

    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)

    if match:
        state_value = match.group(1).strip()
        logger.debug("找到 window.__INITIAL_STATE__:")
        return state_value
    return None


def extract_play_info(html_content: str) -> Optional[str]:
    """
    快速提取HTML文件中的window.__INITIAL_STATE__

    Args:
        html_content (str): HTML文档

    Returns:
        Optional[str]: 提取到的状态值，如果未找到则返回None
    """
    pattern = r'<script[^>]*>.*?window\.__playinfo__\s*=\s*(.+?)(?=\s*;|\s*</script>|\s*$).*?</script>'

    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)

    if match:
        state_value = match.group(1).strip()
        logger.debug("找到 window.__playinfo__:")
        return state_value
    return None

class VideoDetailsNetService(NetService[BiliVideoDetails]):
    """
    Bilibili视频详细信息抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[BiliVideoDetails](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/www.bilibili.com/video/BV.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def detach(self) -> None:
        self.state = None
        await self._net_helper.stop()
        self._net_helper = None
        await super().detach()

    async def invoke(self, extra_params: Dict[str, Any]) -> List[BiliVideoDetails]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(extra_params)

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params,
                                                 pause_ms=pause, extra=extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            delegate=self.loop_delegate,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: str,
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[BiliVideoDetails]:
        data_js = extract_initial_state(payload)
        play_js = extract_play_info(payload)
        if data_js and play_js:
            data = await self.page.evaluate(f"window.__INITIAL_STATE__ = {data_js}")
            play = await self.page.evaluate(f"window.__playinfo__ = {play_js}")
            video = data.get("videoData")
            id = data.get("aid")
            bvid = data.get("bvid")
            cover = video.get("pic")
            ctime = video.get("ctime")
            pubdate = video.get("pubdate")
            duration_sec = video.get("duration")
            intro = video.get("desc")
            title = video.get("title")
            creator = video.get("owner")
            tname = video.get("tname")
            tname_v2 = video.get("tname_v2")
            stat = video.get("stat")
            view = stat.get("view")
            danmaku = stat.get("danmaku")
            reply = stat.get("reply")
            favorite = stat.get("favorite")
            coin = stat.get("coin")
            share = stat.get("share")
            like = stat.get("like")
            dimension = video.get("dimension")
            width = dimension.get("width")
            height = dimension.get("height")
            rotate = dimension.get("rotate")
            tags = data.get("rcmdTabNames")

            video_url_data = play.get("data").get("dash").get("video")[0]
            audio_url_data = play.get("data").get("dash").get("audio")[0]

            video_url = VideoUrl(
                id=video_url_data.get("id"),
                base_url=video_url_data.get("base_url"),
                backup_url=video_url_data.get("backup_url"),
                bandwidth=video_url_data.get("bandwidth"),
                mime_type=video_url_data.get("mime_type"),
                codecs=video_url_data.get("codecs"),
                width=video_url_data.get("width"),
                height=video_url_data.get("height"),
                frame_rate=video_url_data.get("frame_rate"),
                raw_data=self._inject_raw_data(play)
            )
            audio_url = AudioUrl(
                id=audio_url_data.get("id"),
                base_url=audio_url_data.get("base_url"),
                backup_url=audio_url_data.get("backup_url"),
                bandwidth=audio_url_data.get("bandwidth"),
                mime_type=audio_url_data.get("mime_type"),
                codecs=audio_url_data.get("codecs"),
                raw_data=self._inject_raw_data(play)
            )

            return [
                BiliVideoDetails(
                    id=video,
                    bvid=bvid,
                    cover=cover,
                    ctime=ctime,
                    pubdate=pubdate,
                    duration_sec=duration_sec,
                    intro=intro,
                    title=title,
                    creator=AuthorInfo(
                        username=creator.get("name"),
                        user_id=creator.get("mid"),
                        avatar=creator.get("face"),
                    ),
                    tname=tname,
                    tname_v2=tname_v2,
                    stat=VideoStatistic(
                        view=view,
                        danmaku=danmaku,
                        reply=reply,
                        favorite=favorite,
                        coin=coin,
                        share=share,
                        like=like,
                    ),
                    tags=tags,
                    dimension=VideoDimension(
                        width=width,
                        height=height,
                        rotate=rotate,
                    ),
                    video_url=video_url,
                    audio_url=audio_url,
                    raw_data=self._inject_raw_data(data),
                )
            ]

