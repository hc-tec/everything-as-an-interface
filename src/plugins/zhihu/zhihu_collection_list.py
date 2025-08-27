
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
from src.services.zhihu.collection_list_net import CollectionListNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.zhihu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "zhihu_collection_list"


class ZhihuCollectionListPlugin(BasePlugin):

    @dataclass
    class Params:
        user_id: Optional[str]

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = "https://www.zhihu.com/"
    PLATFORM_ID = "zhihu"
    LOGGED_IN_SELECTORS = [
        "#Popover4-toggle",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "1.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Zhihu Collection List plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[ZhihuCollectionListPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._service: Optional[CollectionListNetService] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._service = CollectionListNetService()

            # Attach all services to the page
            await self._service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(ZhihuCollectionListPlugin.Params, self.task_params.extra)

            logger.info("CollectionListNetService service initialized and attached")

        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise
        logger.info("启动知乎收藏夹列表插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止知乎收藏夹列表插件")
        return await super().stop()

    async def _cleanup(self) -> None:
        """Detach all services and cleanup resources."""
        services = [
            self._service,
        ]

        for service in services:
            if service:
                try:
                    await service.detach()
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
        if not self._service:
            raise RuntimeError("Services not initialized. Call setup() first.")

        if self.plugin_params.user_id is None:
            await asyncio.sleep(1000)
            avatar = await self.page.wait_for_selector("#Popover16-toggle", timeout=5000)
            await avatar.click()
            await asyncio.sleep(2)
            locator = self.page.locator(".Menu-item").first
            await locator.click()
            await asyncio.sleep(5)
            url = self.page.url
            match = re.search(r"zhihu\.com/people/([^/?#]+)", url)
            if match:
                self.plugin_params.user_id = match.group(1)
        if self.plugin_params.user_id is None:
            raise RuntimeError("User ID not found. Check url correctly.")
        collection_list_page_url = f"{BASE_URL}/people/{self.plugin_params.user_id}/collections"
        await self.page.goto(collection_list_page_url)
        await asyncio.sleep(1)

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
def create_plugin(ctx: PluginContext, params: TaskParams) -> ZhihuCollectionListPlugin:
    p = ZhihuCollectionListPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
