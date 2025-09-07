from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.bilibili.video_ai_subtitle_net import VideoAiSubtitleNetService
from src.services.bilibili.video_details_net import VideoDetailsNetService
from src.services.collection_common import CollectionState
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.bilibili.com"
LOGIN_URL = f"{BASE_URL}"

PLUGIN_ID = "bilibili_video_details"


class BilibiliVideoDetailsPlugin(BasePlugin):

    @dataclass
    class Params:
        bvid: str

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = LOGIN_URL
    PLATFORM_ID = "bilibili"
    LOGGED_IN_SELECTORS = [
        ".bili-avatar-img",
        ".bili-avatar",
        ".header-entry-mini",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "1.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Bilibili Videos Details plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[BilibiliVideoDetailsPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._details_service: Optional[VideoDetailsNetService] = None
        self._subtitle_service: Optional[VideoAiSubtitleNetService] = None
    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            await self._dont_open_new_page()
            self._details_service = VideoDetailsNetService()
            self._subtitle_service = VideoAiSubtitleNetService()
            # Attach all services to the page
            await self._details_service.attach(self.page)
            await self._subtitle_service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(BilibiliVideoDetailsPlugin.Params, self.task_params.extra)

            logger.info(f"{self._details_service.__class__.__name__} service initialized and attached")
            logger.info(f"{self._subtitle_service.__class__.__name__} service initialized and attached")

        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise
        logger.info("启动插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止插件")
        return await super().stop()

    async def _cleanup(self) -> None:
        """Detach all services and cleanup resources."""
        if self._details_service and self._subtitle_service:
            try:
                await self._details_service.detach()
                await self._subtitle_service.detach()
            except Exception as e:
                logger.warning(f"Service detach failed: {e}")

        logger.info("All services detached and cleaned up")

    async def fetch(self) -> Dict[str, Any]:
        """
        Main fetch method that orchestrates data collection using services.

        Returns:
            Dictionary containing collected data and metadata
        """

        await self._ensure_logged_in()
        self._details_service.set_params(self.task_params.extra)
        self._subtitle_service.set_params(self.task_params.extra)

        try:
            details_res = await self._collect_details()
            subtitle_res = await self._collect_subtitles()
            if details_res["success"] and subtitle_res["success"]:
                return self._response.ok({
                    "details": details_res,
                    "subtitles": subtitle_res,
                })
            raise Exception([details_res.get("error"), subtitle_res.get("error")])

        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return self._response.fail(error=str(e))

    async def _make_stop_decision(self,
                                  loop_count,
                                  extra_params,
                                  page,
                                  state: CollectionState,
                                  *args, **kwargs):
        return StopDecision(should_stop=True, reason="Execute once")

    async def _collect_details(self) -> Dict[str, Any]:

        url = f"https://www.bilibili.com/video/{self.plugin_params.bvid}/?spm_id_from=333.788.recommend_more_video.0&vd_source=6b3d0e6973059f202bf441d103fce535"
        await self.page.goto(url, wait_until="load")
        self._details_service.set_stop_decider(self._make_stop_decision)

        items = await self._details_service.invoke(self.task_params.extra)

        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} results")

        return self._response.ok(items_data[0])

    async def _collect_subtitles(self) -> Dict[str, Any]:
        try:
            locator = await self.page.wait_for_selector(".bpx-player-ctrl-subtitle", timeout=2000)
        except Exception as e:
            return self._response.fail(error="本视频没有AI字幕")
        await locator.click()
        self._subtitle_service.set_stop_decider(self._make_stop_decision)

        items = await self._subtitle_service.invoke(self.task_params.extra)

        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} results")

        return self._response.ok(items_data[0])


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> BilibiliVideoDetailsPlugin:
    p = BilibiliVideoDetailsPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
