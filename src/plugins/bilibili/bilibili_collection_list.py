
import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.bilibili.collection_list_net import CollectionListNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.bilibili.com"
LOGIN_URL = f"{BASE_URL}"

PLUGIN_ID = "bilibili_collection_list"


class BilibiliCollectionListPlugin(BasePlugin):

    @dataclass
    class Params:
        user_id: Optional[str]

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
    PLUGIN_DESCRIPTION: str = f"Bilibili Collection List plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[BilibiliCollectionListPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._service: Optional[CollectionListNetService] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            await self._dont_open_new_page()
            self._service = CollectionListNetService()
            # Attach all services to the page
            await self._service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(BilibiliCollectionListPlugin.Params, self.task_params.extra)

            logger.info("CollectionListNetService service initialized and attached")

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

    async def _collect(self) -> Dict[str, Any]:
        if self.plugin_params.user_id is None:
            # 跳转到自己的个人空间中
            avatar = await self.page.wait_for_selector(".header-entry-mini", timeout=5000)
            await avatar.click()
            await asyncio.sleep(1)
            await self.page.wait_for_load_state("load")
            url = self.page.url
            self._service.set_stop_decider(lambda *args, **kwargs: StopDecision(should_stop=True, reason="Collection Ready"))
            match = re.search(r"https?://space\.bilibili\.com/(\d+)", url)
            if match:
                self.plugin_params.user_id = match.group(1)
            else:
                raise RuntimeError("User ID not found. Check url correctly.")
        else:
            # 跳转到其他人的个人空间中
            pass

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
def create_plugin(ctx: PluginContext, params: TaskParams) -> BilibiliCollectionListPlugin:
    p = BilibiliCollectionListPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
