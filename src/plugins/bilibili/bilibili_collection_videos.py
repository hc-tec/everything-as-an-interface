
import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, List

from playwright.async_api import ElementHandle

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.bilibili.collection_videos_net import CollectionVideoNetService
from src.services.collection_common import CollectionState
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.bilibili.com"
LOGIN_URL = f"{BASE_URL}"

PLUGIN_ID = "bilibili_collection_videos"


class BilibiliCollectionVideosPlugin(BasePlugin):

    @dataclass
    class Params:
        collection_id: Optional[str] # 传入需要获取的收藏夹ID列表
        user_id: Optional[str] = None
        total_page: Optional[int] = None

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
    PLUGIN_DESCRIPTION: str = f"Bilibili Collection Videos plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[BilibiliCollectionVideosPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._service: Optional[CollectionVideoNetService] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            await self._dont_open_new_page()
            self._service = CollectionVideoNetService()
            # Attach all services to the page
            await self._service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(BilibiliCollectionVideosPlugin.Params, self.task_params.extra)

            logger.info("CollectionVideoNetService service initialized and attached")

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
        if self._service:
            try:
                await self._service.detach()
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
        self._service.set_params(self.task_params.extra)
        try:
            res = await self._collect()
            if res["success"]:
                return {
                    "success": True,
                    "data": res["data"],
                    "count": len(res["data"]),
                    "plugin_id": PLUGIN_ID,
                    "version": self.PLUGIN_VERSION,
                }
            raise Exception(res["error"])

        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }

    async def _make_stop_decision(self,
                                  loop_count,
                                  extra_params,
                                  page,
                                  state: CollectionState,
                                  *args, **kwargs):
        if loop_count >= self.plugin_params.total_page:
            return StopDecision(should_stop=True, reason="Reach max collection count")
        return StopDecision(should_stop=False, reason="Don't reach max collection count")

    async def _get_total_page_num(self):
        logger.debug("尝试获取当前收藏夹的总页数")
        try:
            btn = await self.page.wait_for_selector("div.vui_pagenation--btns button:nth-last-of-type(2)", timeout=2000)
            total_page_num = int(await btn.text_content())
            self.plugin_params.total_page = total_page_num
        except Exception as e:
            self.plugin_params.total_page = 1

    async def _click_to_next_page(self,
                                  loop_count: int,
                                  extra_params: Dict[str, Any],
                                  state: CollectionState):
        logger.debug("进入下一页")
        try:
            input_ = await self.page.wait_for_selector(".vui_pagenation-go input", timeout=200)
            await input_.type(str(loop_count+1))
            await input_.press("Enter")
        except Exception as e:
            pass

    async def _collect(self) -> Dict[str, Any]:
        if self.plugin_params.user_id is None:
            # 跳转到自己的个人空间中
            avatar = await self.page.wait_for_selector(".header-entry-mini", timeout=5000)
            await avatar.click()
            await asyncio.sleep(1)
            await self.page.wait_for_load_state("load")
            url = self.page.url
            match = re.search(r"https?://space\.bilibili\.com/(\d+)", url)
            if match:
                self.plugin_params.user_id = match.group(1)
            else:
                raise RuntimeError("User ID not found. Check url correctly.")
        else:
            # 直接跳转到个人空间中
            pass

        user_id = self.plugin_params.user_id
        collection_id = self.plugin_params.collection_id
        url = f"https://space.bilibili.com/{user_id}/favlist?fid={collection_id}&ftype=create"
        await self.page.goto(url, wait_until="load")

        await self._get_total_page_num()

        self._service.set_stop_decider(self._make_stop_decision)
        self._service.set_delegate_on_loop_item_end(self._click_to_next_page)
        try:
            items = await self._service.invoke(self.task_params.extra)

            # Convert to dictionaries for JSON serialization
            items_data = [asdict(item) for item in items]

            logger.info(f"Successfully collected {len(items_data)} search results")

            return {
                "success": True,
                "data": items_data,
                "count": len(items_data),
                "task_type": "briefs",
            }

        except Exception as e:
            logger.error(f"Briefs collection failed: {e}")
            return {
                "success": False,
                "data": None,
                "count": 0,
                "task_type": "briefs",
                "error": str(e),
            }


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> BilibiliCollectionVideosPlugin:
    p = BilibiliCollectionVideosPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
