"""
Xiaohongshu Plugin V2 - Service-based Architecture

This is a thin plugin that orchestrates calls to various Xiaohongshu site services.
The plugin focuses on configuration, coordination, and output formatting,
while delegating specific tasks to specialized services.
"""

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.xiaohongshu.note_search_net import XiaohongshuNoteSearchNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_search"


class XiaohongshuNoteSearchPlugin(BasePlugin):

    @dataclass
    class Params:
        search_words: str

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = "https://www.xiaohongshu.com/login"
    PLATFORM_ID = "xiaohongshu"
    LOGGED_IN_SELECTORS = [
        ".reds-img-box",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "2.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu note search plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[XiaohongshuNoteSearchPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._note_search_net_service: Optional[XiaohongshuNoteSearchNetService] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._note_search_net_service = XiaohongshuNoteSearchNetService()

            # Attach all services to the page
            await self._note_search_net_service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(XiaohongshuNoteSearchPlugin.Params, self.task_params.extra)

            logger.info(f"{self._note_search_net_service.__class__.__name__} service initialized and attached")

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
        services = [
            self._note_search_net_service,
        ]
        
        for service in services:
            if service:
                try:
                    await service.detach()
                except Exception as e:
                    logger.warning(f"Service detach failed: {e}")
        
        logger.info("All services detached and cleaned up")

    def validate_params(self) -> Dict[str, Any]:
        if self.plugin_params.search_words is None:
            return { "valid": False, "errors": ["You should provide search_words in TaskParams"] }
        return { "valid": True, "errors": [] }

    async def fetch(self) -> Dict[str, Any]:
        """
        Main fetch method that orchestrates data collection using services.
        
        Returns:
            Dictionary containing collected data and metadata
        """

        await self._ensure_logged_in()
        self._note_search_net_service.set_params(self.task_params.extra)

        try:
            briefs_res = await self._collect_briefs()
            if briefs_res["success"]:
                return self._response.ok(data=briefs_res["data"])
            raise Exception(briefs_res["error"])
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return self._response.fail(error=str(e))

    async def _collect_briefs(self) -> Dict[str, Any]:
        if not self._note_search_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")

        search_words = self.plugin_params.search_words
        url = f"https://www.xiaohongshu.com/search_result?keyword={search_words}&source=web_search_result_notes"
        await self.page.goto(url, wait_until="load")
        await asyncio.sleep(1)

        items = await self._note_search_net_service.invoke(self.task_params.extra)

        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} results")

        return self._response.ok(data=items_data)


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuNoteSearchPlugin:
    p = XiaohongshuNoteSearchPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
